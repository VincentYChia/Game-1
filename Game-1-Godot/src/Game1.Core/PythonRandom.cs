using System.Numerics;

namespace Game1.Core;

/// <summary>
/// Python-exact random.Random (ADR-5): MT19937 with CPython's init_by_array
/// integer seeding (absolute value, little-endian 32-bit words), random(),
/// getrandbits (little-endian word assembly, top word truncated), _randbelow
/// rejection sampling, choice/randint/shuffle/uniform. Pinned bit-for-bit by
/// conformance/goldens/db_parity/python_rng.json. This is the keystone for
/// deterministic parity everywhere Python uses seeded RNG (spawn-area chunk
/// types, per-chunk resource rolls, village generation, crux scenarios).
/// </summary>
public sealed class PythonRandom
{
    private const int N = 624, M = 397;
    private const uint MatrixA = 0x9908b0dfu, UpperMask = 0x80000000u, LowerMask = 0x7fffffffu;

    private readonly uint[] _mt = new uint[N];
    private int _mti = N + 1;

    public PythonRandom(long seed) : this(new BigInteger(seed)) { }

    public PythonRandom(BigInteger seed)
    {
        if (seed < 0) seed = -seed;  // CPython random_seed: PyNumber_Absolute
        var key = new List<uint>();
        if (seed.IsZero)
            key.Add(0);
        else
            while (seed > 0)
            {
                key.Add((uint)(seed & 0xffffffff));
                seed >>= 32;
            }
        InitByArray(key);
    }

    private void InitGenrand(uint s)
    {
        _mt[0] = s;
        for (_mti = 1; _mti < N; _mti++)
            _mt[_mti] = (uint)(1812433253u * (_mt[_mti - 1] ^ (_mt[_mti - 1] >> 30)) + (uint)_mti);
    }

    private void InitByArray(List<uint> key)
    {
        InitGenrand(19650218u);
        int i = 1, j = 0;
        var k = Math.Max(N, key.Count);
        for (; k > 0; k--)
        {
            _mt[i] = (uint)((_mt[i] ^ ((_mt[i - 1] ^ (_mt[i - 1] >> 30)) * 1664525u))
                            + key[j] + (uint)j);
            i++; j++;
            if (i >= N) { _mt[0] = _mt[N - 1]; i = 1; }
            if (j >= key.Count) j = 0;
        }
        for (k = N - 1; k > 0; k--)
        {
            _mt[i] = (uint)((_mt[i] ^ ((_mt[i - 1] ^ (_mt[i - 1] >> 30)) * 1566083941u))
                            - (uint)i);
            i++;
            if (i >= N) { _mt[0] = _mt[N - 1]; i = 1; }
        }
        _mt[0] = 0x80000000u;
    }

    public uint GenrandUInt32()
    {
        uint y;
        if (_mti >= N)
        {
            int kk;
            for (kk = 0; kk < N - M; kk++)
            {
                y = (_mt[kk] & UpperMask) | (_mt[kk + 1] & LowerMask);
                _mt[kk] = _mt[kk + M] ^ (y >> 1) ^ ((y & 1) != 0 ? MatrixA : 0u);
            }
            for (; kk < N - 1; kk++)
            {
                y = (_mt[kk] & UpperMask) | (_mt[kk + 1] & LowerMask);
                _mt[kk] = _mt[kk + (M - N)] ^ (y >> 1) ^ ((y & 1) != 0 ? MatrixA : 0u);
            }
            y = (_mt[N - 1] & UpperMask) | (_mt[0] & LowerMask);
            _mt[N - 1] = _mt[M - 1] ^ (y >> 1) ^ ((y & 1) != 0 ? MatrixA : 0u);
            _mti = 0;
        }
        y = _mt[_mti++];
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680u;
        y ^= (y << 15) & 0xefc60000u;
        y ^= y >> 18;
        return y;
    }

    /// <summary>CPython random_random: 53-bit double in [0, 1).</summary>
    public double NextDouble()
    {
        var a = GenrandUInt32() >> 5;
        var b = GenrandUInt32() >> 6;
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    }

    /// <summary>CPython getrandbits for k in [1, 64]: little-endian 32-bit
    /// words, each word top-truncated to remaining bits.</summary>
    public ulong GetRandBits(int k)
    {
        if (k is < 1 or > 64)
            throw new ArgumentOutOfRangeException(nameof(k));
        if (k <= 32)
            return GenrandUInt32() >> (32 - k);
        ulong result = 0;
        var shift = 0;
        while (k > 0)
        {
            ulong r = GenrandUInt32();
            if (k < 32)
                r >>= 32 - k;
            result |= r << shift;
            shift += 32;
            k -= 32;
        }
        return result;
    }

    /// <summary>CPython _randbelow_with_getrandbits: rejection sampling.</summary>
    public long RandBelow(long n)
    {
        if (n <= 0) return 0;
        var k = 64 - System.Numerics.BitOperations.LeadingZeroCount((ulong)n);
        var r = (long)GetRandBits(k);
        while (r >= n)
            r = (long)GetRandBits(k);
        return r;
    }

    public long RandInt(long a, long b) => a + RandBelow(b - a + 1);

    public T Choice<T>(IReadOnlyList<T> seq) => seq[(int)RandBelow(seq.Count)];

    /// <summary>random.shuffle: Fisher-Yates from the top, _randbelow indices.</summary>
    public void Shuffle<T>(IList<T> x)
    {
        for (var i = x.Count - 1; i > 0; i--)
        {
            var j = (int)RandBelow(i + 1);
            (x[i], x[j]) = (x[j], x[i]);
        }
    }

    public double Uniform(double a, double b) => a + (b - a) * NextDouble();

    /// <summary>CPython random.sample: pool partial-shuffle for small n,
    /// rejection set for large n. The setsize crossover (21 + 4^ceil(log4(3k))
    /// for k>5) must match exactly — it changes which draws occur. Powers of
    /// 4 are never multiples of 3, so the ceil never sits on an exact-power
    /// float boundary.</summary>
    public List<T> Sample<T>(IReadOnlyList<T> population, int k)
    {
        var n = population.Count;
        if (k < 0 || k > n)
            throw new ArgumentException("Sample larger than population or is negative");
        var result = new T[k];
        var setsize = 21.0;
        if (k > 5)
            setsize += Math.Pow(4, Math.Ceiling(Math.Log(k * 3) / Math.Log(4)));
        if (n <= setsize)
        {
            var pool = population.ToList();
            for (var i = 0; i < k; i++)
            {
                var j = (int)RandBelow(n - i);
                result[i] = pool[j];
                pool[j] = pool[n - i - 1];
            }
        }
        else
        {
            var selected = new HashSet<long>();
            for (var i = 0; i < k; i++)
            {
                var j = RandBelow(n);
                while (selected.Contains(j))
                    j = RandBelow(n);
                selected.Add(j);
                result[i] = population[(int)j];
            }
        }
        return result.ToList();
    }
}
