# Python to C# Language Mapping Reference

**Purpose**: Comprehensive reference for the migration team when converting Python/Pygame code to C#/Unity.
**Audience**: Developers actively porting Game-1 code.
**Created**: 2026-02-10

---

## 1. Type Mappings

### 1.1 Primitive Types

| Python Type | C# Type | Notes |
|-------------|---------|-------|
| `int` | `int` | Python int is arbitrary precision; C# int is 32-bit. Use `long` if values exceed 2^31. |
| `float` | `float` | Python float is 64-bit (IEEE 754 double). C# `float` is 32-bit. Unity uses `float` for performance. Accept minor precision differences. |
| `str` | `string` | C# strings are reference types and can be null. Python strings cannot be None unless explicitly typed Optional. |
| `bool` | `bool` | Identical semantics. |
| `None` | `null` | C# reference types are nullable by default. For value types, use `T?` (e.g., `int?`, `float?`). |
| `bytes` | `byte[]` | Direct equivalent. |
| `complex` | Not used | Not present in Game-1 codebase. |

### 1.2 Collection Types

| Python Type | C# Type | Notes |
|-------------|---------|-------|
| `list` | `List<T>` | `System.Collections.Generic.List<T>`. Mutable, ordered. |
| `dict` | `Dictionary<TKey, TValue>` | `System.Collections.Generic.Dictionary<TKey, TValue>`. |
| `set` | `HashSet<T>` | `System.Collections.Generic.HashSet<T>`. |
| `tuple` | `(T1, T2)` or `Vector2Int` | C# value tuples for general use. `Vector2Int` for grid coordinates in Unity. |
| `Position(x, y)` | `GamePosition` | **IMPORTANT**: Python `y` = Unity `z`. Use `GamePosition.FromXZ(x, y)`. Y (height) defaults to 0. See Phase 1 / IMPROVEMENTS.md Part 6. |
| `frozenset` | `ImmutableHashSet<T>` | Requires `System.Collections.Immutable`. Rarely needed. |
| `deque` | `Queue<T>` or `LinkedList<T>` | `Queue<T>` for FIFO. `LinkedList<T>` for both ends. |

### 1.3 Typing Module Equivalents

| Python Type Hint | C# Type | Notes |
|------------------|---------|-------|
| `Optional[T]` | `T?` (nullable) | For value types: `int?`. For reference types: `string?` (nullable reference types in C# 8+). |
| `Union[str, int]` | `object` or overloads | No direct equivalent. Use method overloading or a discriminated union pattern. |
| `List[T]` | `List<T>` | Direct mapping. |
| `Dict[str, T]` | `Dictionary<string, T>` | Direct mapping. |
| `Tuple[int, int]` | `(int, int)` | Named tuples: `(int x, int y)`. |
| `Set[str]` | `HashSet<string>` | Direct mapping. |
| `Any` | `object` | Avoid when possible. Use generics or specific interfaces. |
| `Callable[[int], str]` | `Func<int, string>` | Or `Action<int>` for void return. |
| `Iterator[T]` | `IEnumerable<T>` | Use with `yield return` in C#. |

---

## 2. Pattern Mappings

### 2.1 Common Syntax

| Python Pattern | C# Pattern |
|----------------|------------|
| `@dataclass` | `[Serializable] class` or `record` (C# 9+) |
| `__post_init__(self)` | Constructor body (after field assignments) |
| `field(default_factory=list)` | `= new List<T>()` in constructor or field initializer |
| `@classmethod` | `static` method |
| `@staticmethod` | `static` method |
| `@property` | C# property: `public T Prop { get; }` or `public T Prop { get; set; }` |
| `@property` with setter | `public T Prop { get; set; }` |
| `@abstractmethod` | `abstract` method in `abstract class`, or interface method |
| `isinstance(x, T)` | `x is T` (pattern matching) |
| `hasattr(x, "prop")` | `x is IHasProp` (interface check) or reflection (avoid) |
| `getattr(x, "prop", default)` | `x?.Prop ?? default` (null-conditional + null-coalescing) |
| `x.__class__.__name__` | `x.GetType().Name` |
| `type(x).__name__` | `x.GetType().Name` |

### 2.2 Iteration Patterns

| Python Pattern | C# Pattern |
|----------------|------------|
| `for item in list:` | `foreach (var item in list)` |
| `for i, item in enumerate(list):` | `for (int i = 0; i < list.Count; i++) { var item = list[i]; }` |
| `for k, v in dict.items():` | `foreach (var (k, v) in dict)` or `foreach (var kvp in dict)` |
| `for k in dict:` | `foreach (var k in dict.Keys)` |
| `for v in dict.values():` | `foreach (var v in dict.Values)` |
| `range(n)` | `Enumerable.Range(0, n)` or `for (int i = 0; i < n; i++)` |
| `range(a, b)` | `Enumerable.Range(a, b - a)` or `for (int i = a; i < b; i++)` |
| `zip(list1, list2)` | `list1.Zip(list2, (a, b) => (a, b))` |

### 2.3 Comprehensions and LINQ

| Python Pattern | C# Pattern |
|----------------|------------|
| `[x*2 for x in items]` | `items.Select(x => x * 2).ToList()` |
| `[x for x in items if x > 0]` | `items.Where(x => x > 0).ToList()` |
| `{k: v for k, v in items}` | `items.ToDictionary(x => x.k, x => x.v)` |
| `{x for x in items}` | `new HashSet<T>(items)` or `items.ToHashSet()` |
| `any(x > 0 for x in items)` | `items.Any(x => x > 0)` |
| `all(x > 0 for x in items)` | `items.All(x => x > 0)` |
| `sum(items)` | `items.Sum()` |
| `max(items)` | `items.Max()` |
| `min(items)` | `items.Min()` |
| `len(items)` | `items.Count` (List) or `items.Length` (array) |
| `sorted(items)` | `items.OrderBy(x => x).ToList()` |
| `sorted(items, key=lambda x: x.name)` | `items.OrderBy(x => x.Name).ToList()` |
| `sorted(items, reverse=True)` | `items.OrderByDescending(x => x).ToList()` |

### 2.4 String Operations

| Python Pattern | C# Pattern |
|----------------|------------|
| `f"Hello {name}"` | `$"Hello {name}"` (string interpolation) |
| `f"{value:.2f}"` | `$"{value:F2}"` |
| `"text".upper()` | `"text".ToUpper()` |
| `"text".lower()` | `"text".ToLower()` |
| `"text".strip()` | `"text".Trim()` |
| `"text".startswith("t")` | `"text".StartsWith("t")` |
| `"text".endswith("t")` | `"text".EndsWith("t")` |
| `"a,b,c".split(",")` | `"a,b,c".Split(',')` |
| `",".join(items)` | `string.Join(",", items)` |
| `"text".replace("a", "b")` | `"text".Replace("a", "b")` |
| `"text" in string` | `string.Contains("text")` |

### 2.5 Error Handling

| Python Pattern | C# Pattern |
|----------------|------------|
| `try: ... except Exception as e:` | `try { ... } catch (Exception e) { ... }` |
| `try: ... except (TypeError, ValueError):` | `try { ... } catch (Exception e) when (e is InvalidCastException or ArgumentException) { ... }` |
| `try: ... finally:` | `try { ... } finally { ... }` |
| `raise Exception("msg")` | `throw new Exception("msg")` |
| `raise ValueError("msg")` | `throw new ArgumentException("msg")` |
| `raise NotImplementedError` | `throw new NotImplementedException()` |
| `with open(f) as file:` | `using (var stream = File.OpenRead(f)) { ... }` |

### 2.6 Math and Random

| Python Pattern | C# Pattern |
|----------------|------------|
| `random.random()` | `UnityEngine.Random.value` (0.0 to 1.0) |
| `random.randint(a, b)` | `UnityEngine.Random.Range(a, b + 1)` (b+1 because Unity Range is exclusive on upper bound for ints) |
| `random.uniform(a, b)` | `UnityEngine.Random.Range(a, b)` (inclusive on both for floats) |
| `random.choice(items)` | `items[UnityEngine.Random.Range(0, items.Count)]` |
| `random.choices(items, weights)` | Custom weighted random (no built-in equivalent) |
| `random.shuffle(items)` | Fisher-Yates shuffle (no built-in; implement manually) |
| `math.floor(x)` | `Mathf.FloorToInt(x)` |
| `math.ceil(x)` | `Mathf.CeilToInt(x)` |
| `math.sqrt(x)` | `Mathf.Sqrt(x)` |
| `math.exp(x)` | `Mathf.Exp(x)` |
| `math.log(x)` | `Mathf.Log(x)` |
| `math.pow(x, y)` | `Mathf.Pow(x, y)` |
| `math.pi` | `Mathf.PI` |
| `abs(x)` | `Mathf.Abs(x)` |
| `max(a, b)` | `Mathf.Max(a, b)` |
| `min(a, b)` | `Mathf.Min(a, b)` |
| `round(x)` | `Mathf.RoundToInt(x)` |
| `int(x)` (truncate) | `(int)x` (truncates toward zero) |

### 2.7 Time

| Python Pattern | C# (Unity) Pattern |
|----------------|---------------------|
| `time.time()` | `Time.time` (seconds since game start, float) |
| `pygame.time.get_ticks()` | `Time.time * 1000f` or `Time.realtimeSinceStartup * 1000f` |
| `time.sleep(seconds)` | `await Task.Delay(milliseconds)` or coroutine `yield return new WaitForSeconds(seconds)` |
| `datetime.now()` | `System.DateTime.Now` |

---

## 3. Singleton Pattern Migration

### 3.1 Python Singleton

```python
class MaterialDatabase:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self):
        # Load data from JSON files
        with open("items.JSON/items-materials-1.JSON") as f:
            data = json.load(f)
        self.materials = {}
        for item in data:
            self.materials[item["materialId"]] = item
```

### 3.2 C# Singleton (Thread-Safe Lazy)

```csharp
public class MaterialDatabase
{
    private static readonly Lazy<MaterialDatabase> _instance =
        new Lazy<MaterialDatabase>(() =>
        {
            var db = new MaterialDatabase();
            db.Load();
            return db;
        });

    public static MaterialDatabase Instance => _instance.Value;

    private Dictionary<string, MaterialDefinition> _materials;

    // Private constructor prevents external instantiation
    private MaterialDatabase() { }

    private void Load()
    {
        string json = Resources.Load<TextAsset>("JSON/items-materials-1").text;
        var items = JsonConvert.DeserializeObject<List<MaterialDefinition>>(json);
        _materials = items.ToDictionary(m => m.MaterialId);
    }

    public MaterialDefinition GetMaterial(string materialId)
    {
        return _materials.TryGetValue(materialId, out var mat) ? mat : null;
    }

    public int Count => _materials.Count;
}
```

### 3.3 Key Differences

| Aspect | Python | C# |
|--------|--------|-----|
| Thread safety | Not thread-safe by default | `Lazy<T>` guarantees thread-safe initialization |
| Initialization timing | First call to `get_instance()` | First access to `Instance` property |
| File I/O | `open()` with path string | `Resources.Load<TextAsset>()` for Unity |
| Null check | `if cls._instance is None` | Handled by `Lazy<T>` internally |
| Testing | Replace `_instance` directly | Use interface + DI for testability |

---

## 4. Enum Migration

### 4.1 Python Enum with String Values

```python
from enum import Enum

class CraftingDiscipline(Enum):
    SMITHING = "smithing"
    ALCHEMY = "alchemy"
    REFINING = "refining"
    ENGINEERING = "engineering"
    ENCHANTING = "enchanting"

# Usage:
discipline = CraftingDiscipline.SMITHING
print(discipline.value)  # "smithing"
if discipline == CraftingDiscipline.SMITHING:
    do_something()
```

### 4.2 C# Enum with Extension Methods

```csharp
public enum CraftingDiscipline
{
    Smithing,
    Alchemy,
    Refining,
    Engineering,
    Enchanting
}

public static class CraftingDisciplineExtensions
{
    private static readonly Dictionary<CraftingDiscipline, string> _values = new()
    {
        { CraftingDiscipline.Smithing, "smithing" },
        { CraftingDiscipline.Alchemy, "alchemy" },
        { CraftingDiscipline.Refining, "refining" },
        { CraftingDiscipline.Engineering, "engineering" },
        { CraftingDiscipline.Enchanting, "enchanting" }
    };

    private static readonly Dictionary<string, CraftingDiscipline> _reverse =
        _values.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

    /// <summary>Get the string value matching the Python enum's .value property.</summary>
    public static string ToValue(this CraftingDiscipline discipline)
        => _values[discipline];

    /// <summary>Parse a string value into an enum. Throws if not found.</summary>
    public static CraftingDiscipline FromValue(string value)
        => _reverse[value];

    /// <summary>Try to parse a string value. Returns false if not found.</summary>
    public static bool TryFromValue(string value, out CraftingDiscipline result)
        => _reverse.TryGetValue(value, out result);
}

// Usage:
var discipline = CraftingDiscipline.Smithing;
string value = discipline.ToValue();  // "smithing"
var parsed = CraftingDisciplineExtensions.FromValue("smithing");
```

### 4.3 JSON Deserialization with Enums

When deserializing JSON that uses string values (matching Python's enum `.value`):

```csharp
// Custom JSON converter for Newtonsoft.Json
public class DisciplineConverter : JsonConverter<CraftingDiscipline>
{
    public override CraftingDiscipline ReadJson(JsonReader reader, Type objectType,
        CraftingDiscipline existingValue, bool hasExistingValue, JsonSerializer serializer)
    {
        string value = reader.Value?.ToString();
        return CraftingDisciplineExtensions.FromValue(value);
    }

    public override void WriteJson(JsonWriter writer, CraftingDiscipline value,
        JsonSerializer serializer)
    {
        writer.WriteValue(value.ToValue());
    }
}
```

---

## 5. Dataclass Migration

### 5.1 Python @dataclass (Full Featured)

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class EquipmentItem:
    item_id: str
    name: str
    tier: int = 1
    damage: int = 0
    defense: int = 0
    durability: int = 100
    max_durability: int = 100
    weight: float = 1.0
    tags: List[str] = field(default_factory=list)
    enchantments: Dict[str, float] = field(default_factory=dict)
    crafted_quality: Optional[str] = None

    def __post_init__(self):
        # Validate tier range
        self.tier = max(1, min(4, self.tier))
        # Ensure durability does not exceed max
        self.durability = min(self.durability, self.max_durability)

    @property
    def effectiveness(self) -> float:
        """Durability-based effectiveness: 50% at 0 durability, 100% at full."""
        return 0.5 + (self.durability / self.max_durability) * 0.5

    @property
    def is_broken(self) -> bool:
        return self.durability <= 0
```

### 5.2 C# [Serializable] Class

```csharp
using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using UnityEngine;

[Serializable]
public class EquipmentItem
{
    [JsonProperty("item_id")]
    public string ItemId { get; set; }

    [JsonProperty("name")]
    public string Name { get; set; }

    [JsonProperty("tier")]
    public int Tier { get; set; } = 1;

    [JsonProperty("damage")]
    public int Damage { get; set; } = 0;

    [JsonProperty("defense")]
    public int Defense { get; set; } = 0;

    [JsonProperty("durability")]
    public int Durability { get; set; } = 100;

    [JsonProperty("max_durability")]
    public int MaxDurability { get; set; } = 100;

    [JsonProperty("weight")]
    public float Weight { get; set; } = 1.0f;

    [JsonProperty("tags")]
    public List<string> Tags { get; set; } = new();

    [JsonProperty("enchantments")]
    public Dictionary<string, float> Enchantments { get; set; } = new();

    [JsonProperty("crafted_quality")]
    public string CraftedQuality { get; set; }  // null when not set

    // Default constructor for deserialization
    public EquipmentItem() { }

    // Full constructor (replaces dataclass auto-generated __init__)
    public EquipmentItem(string itemId, string name, int tier = 1,
                         int damage = 0, int defense = 0,
                         int durability = 100, int maxDurability = 100,
                         float weight = 1.0f, List<string> tags = null,
                         Dictionary<string, float> enchantments = null,
                         string craftedQuality = null)
    {
        ItemId = itemId;
        Name = name;
        Tier = Mathf.Clamp(tier, 1, 4);  // __post_init__ validation
        Damage = damage;
        Defense = defense;
        MaxDurability = maxDurability;
        Durability = Mathf.Min(durability, maxDurability);  // __post_init__ validation
        Weight = weight;
        Tags = tags ?? new List<string>();
        Enchantments = enchantments ?? new Dictionary<string, float>();
        CraftedQuality = craftedQuality;
    }

    /// <summary>
    /// Durability-based effectiveness: 50% at 0 durability, 100% at full.
    /// Formula: 0.5 + (durability / max_durability) * 0.5
    /// </summary>
    public float Effectiveness =>
        0.5f + ((float)Durability / MaxDurability) * 0.5f;

    public bool IsBroken => Durability <= 0;
}
```

### 5.3 Key Migration Notes for Dataclasses

| Python Feature | C# Equivalent | Gotcha |
|----------------|---------------|--------|
| `field(default_factory=list)` | `= new List<T>()` in field initializer | C# creates a new instance per object; Python would share the default if not using `field()`. |
| `__post_init__` | Constructor body after assignments | Must be called in every constructor, including the parameterless one used by JSON deserialization. Consider `[OnDeserialized]` callback. |
| `__eq__` (auto-generated) | Override `Equals()` and `GetHashCode()` | Dataclasses auto-generate equality by value; C# classes use reference equality by default. |
| `__repr__` (auto-generated) | Override `ToString()` | Optional but useful for debugging. |

---

## 6. ABC / Interface Migration

### 6.1 Python ABC with @abstractmethod

```python
from abc import ABC, abstractmethod
from typing import List

class ICraftingMinigame(ABC):
    @abstractmethod
    def start(self, difficulty_params: dict) -> None:
        """Initialize the minigame with difficulty parameters."""
        pass

    @abstractmethod
    def update(self, dt: float) -> None:
        """Update minigame state each frame."""
        pass

    @abstractmethod
    def get_result(self) -> float:
        """Return performance score 0.0 to 1.0."""
        pass

    def is_complete(self) -> bool:
        """Default implementation: check if time has expired."""
        return self.time_remaining <= 0
```

### 6.2 C# Interface + Abstract Class

```csharp
// Interface for the pure contract
public interface ICraftingMinigame
{
    void Start(Dictionary<string, object> difficultyParams);
    void Update(float dt);
    float GetResult();
    bool IsComplete { get; }
}

// Abstract base class for shared implementation
public abstract class CraftingMinigameBase : ICraftingMinigame
{
    protected float TimeRemaining { get; set; }

    public abstract void Start(Dictionary<string, object> difficultyParams);
    public abstract void Update(float dt);
    public abstract float GetResult();

    // Default implementation (matches Python's non-abstract method)
    public virtual bool IsComplete => TimeRemaining <= 0;
}
```

### 6.3 When to Use Interface vs Abstract Class

| Scenario | Use |
|----------|-----|
| Pure contract, no shared code | `interface` |
| Contract + shared default implementations | `abstract class` |
| Multiple inheritance needed | `interface` (C# does not support multiple class inheritance) |
| Python ABC with mix of abstract and concrete methods | `abstract class` implementing an `interface` |

---

## 7. JSON Deserialization

### 7.1 Python json.load()

```python
import json

def load_recipes(filepath: str) -> List[dict]:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

# Nested access with defaults
recipe_name = data.get("name", "Unknown")
inputs = data.get("inputs", [])
tier = data.get("tier", 1)
```

### 7.2 C# Newtonsoft.Json

```csharp
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

// Strongly-typed deserialization
public class Recipe
{
    [JsonProperty("recipeId")]
    public string RecipeId { get; set; }

    [JsonProperty("name")]
    public string Name { get; set; } = "Unknown";

    [JsonProperty("inputs")]
    public List<RecipeInput> Inputs { get; set; } = new();

    [JsonProperty("tier")]
    public int Tier { get; set; } = 1;
}

// Load from Unity Resources
string json = Resources.Load<TextAsset>("JSON/recipes-smithing-3").text;
List<Recipe> recipes = JsonConvert.DeserializeObject<List<Recipe>>(json);

// Load from file path (save system)
string json = File.ReadAllText(filepath, Encoding.UTF8);
SaveData data = JsonConvert.DeserializeObject<SaveData>(json);

// Dynamic access (matching Python dict access)
JObject obj = JObject.Parse(json);
string name = (string)obj["name"] ?? "Unknown";
JArray inputs = (JArray)obj["inputs"] ?? new JArray();
int tier = (int)(obj["tier"] ?? 1);
```

### 7.3 JSON Property Name Mapping

Python uses `snake_case` keys in JSON. C# conventions use `PascalCase` properties. The `[JsonProperty]` attribute bridges this:

```csharp
[JsonProperty("item_id")]         // JSON key: "item_id"
public string ItemId { get; set; } // C# property: ItemId

[JsonProperty("max_durability")]
public int MaxDurability { get; set; }

[JsonProperty("crafted_quality")]
public string CraftedQuality { get; set; }
```

Alternatively, use a global naming strategy:

```csharp
var settings = new JsonSerializerSettings
{
    ContractResolver = new DefaultContractResolver
    {
        NamingStrategy = new SnakeCaseNamingStrategy()
    }
};
var item = JsonConvert.DeserializeObject<EquipmentItem>(json, settings);
```

---

## 8. Common Gotchas

### 8.1 Integer Division

```python
# Python: // is floor division (rounds toward negative infinity)
7 // 2    # = 3  (same as C#)
-7 // 2   # = -4 (DIFFERENT from C#!)
```

```csharp
// C#: / is truncation division (rounds toward zero)
7 / 2     // = 3  (same as Python)
-7 / 2    // = -3 (DIFFERENT from Python!)

// To match Python's floor division:
int FloorDiv(int a, int b)
{
    int result = a / b;
    // Adjust if signs differ and there is a remainder
    if ((a ^ b) < 0 && result * b != a)
        result--;
    return result;
}
```

**Game-1 impact**: The chunk coordinate calculation `chunk_x = floor(world_x / 16)` must use floor division. Negative world coordinates will produce wrong chunk indices if truncation division is used.

### 8.2 Modulo with Negative Numbers

```python
# Python: % always returns a non-negative result when divisor is positive
-7 % 3    # = 2  (DIFFERENT from C#!)
7 % -3    # = -2
```

```csharp
// C#: % preserves the sign of the dividend
-7 % 3    // = -1 (DIFFERENT from Python!)
7 % -3    // = 1

// To match Python's modulo:
int PythonMod(int a, int b) => ((a % b) + b) % b;
```

**Game-1 impact**: Chunk-local tile positions use modulo (`local_x = world_x % 16`). With negative coordinates, C# modulo produces negative indices which will cause array out-of-bounds errors.

### 8.3 List Slicing

```python
items = [1, 2, 3, 4, 5]
items[1:3]     # [2, 3]
items[:3]      # [1, 2, 3]
items[-2:]     # [4, 5]
items[::2]     # [1, 3, 5] (every 2nd)
items[::-1]    # [5, 4, 3, 2, 1] (reverse)
```

```csharp
var items = new List<int> { 1, 2, 3, 4, 5 };
items.GetRange(1, 2);                          // [2, 3]
items.Take(3).ToList();                        // [1, 2, 3]
items.TakeLast(2).ToList();                    // [4, 5]
items.Where((x, i) => i % 2 == 0).ToList();   // [1, 3, 5]
items.AsEnumerable().Reverse().ToList();        // [5, 4, 3, 2, 1]

// For arrays, use Span<T> or ArraySegment<T> for zero-copy slicing:
int[] arr = { 1, 2, 3, 4, 5 };
Span<int> slice = arr.AsSpan(1, 2);  // [2, 3], no allocation
```

### 8.4 Dictionary Default Values

```python
# Python: dict.get(key, default) returns default if key missing
value = d.get("key", 0)

# Python: defaultdict provides automatic defaults
from collections import defaultdict
counts = defaultdict(int)
counts["missing"] += 1  # = 1 (auto-created with int default = 0)
```

```csharp
// C#: TryGetValue + null-coalescing
int value = d.TryGetValue("key", out var v) ? v : 0;

// Or use GetValueOrDefault (available since .NET Core 2.0)
int value = d.GetValueOrDefault("key", 0);

// C#: No built-in defaultdict. Use extension method or manual check:
if (!counts.ContainsKey("missing"))
    counts["missing"] = 0;
counts["missing"] += 1;
```

### 8.5 None Checks vs Null Checks

```python
# Python: None checks
if x is None:
    pass
if x is not None:
    pass
```

```csharp
// C#: null checks for reference types
if (x == null) { }      // Standard null check
if (x != null) { }
if (x is null) { }      // Pattern matching (preferred for exact null check)
if (x is not null) { }

// Unity-specific: UnityEngine.Object overrides == for destroyed objects
// Use ReferenceEquals for true null check, or the == override for "destroyed" check
if (gameObject == null) { }  // True if null OR destroyed
```

### 8.6 Mutable Default Arguments

```python
# CLASSIC PYTHON BUG: Mutable default argument shared across calls
def bad_function(items=[]):
    items.append(1)
    return items

# bad_function() returns [1], [1,1], [1,1,1], etc.

# Correct Python pattern:
def good_function(items=None):
    if items is None:
        items = []
    items.append(1)
    return items
```

```csharp
// C# does NOT have this bug. Default parameter values must be compile-time constants.
// Mutable defaults require null-coalescing:
public List<int> GoodFunction(List<int> items = null)
{
    items ??= new List<int>();  // Creates new list each time if null
    items.Add(1);
    return items;
}
```

**Game-1 impact**: Search the Python codebase for `def method(self, items=[])` or similar patterns. If found, determine whether the shared state is intentional or a bug, and port accordingly.

### 8.7 Floor/Truncation of Negative Floats

```python
# Python: int() truncates toward zero, math.floor() rounds toward negative infinity
int(-0.5)          # = 0  (truncation)
math.floor(-0.5)   # = -1 (floor)
int(0.9)           # = 0  (truncation)
math.floor(0.9)    # = 0  (floor)
```

```csharp
// C#: (int) cast truncates toward zero, Mathf.FloorToInt rounds toward negative infinity
(int)(-0.5f)             // = 0   (truncation)
Mathf.FloorToInt(-0.5f)  // = -1  (floor)
(int)(0.9f)              // = 0   (truncation)
Mathf.FloorToInt(0.9f)   // = 0   (floor)
```

**Game-1 impact**: The coordinate-to-pixel mapping in `AdornmentPreprocessor` uses `int()` in Python (truncation). The chunk coordinate calculation uses `floor()`. Verify which conversion is used at each call site and match the behavior exactly.

### 8.8 Standard Deviation: Population vs Sample

```python
import numpy as np

# NumPy default: population std (ddof=0, divides by N)
np.std([1, 2, 3, 4, 5])  # = 1.4142...

# Python statistics module: sample std (divides by N-1)
import statistics
statistics.stdev([1, 2, 3, 4, 5])  # = 1.5811...
```

```csharp
// No built-in population std in C#. Implement manually:
public static float PopulationStd(List<float> values)
{
    if (values.Count < 2) return 0f;
    float mean = values.Average();
    float sumSquares = values.Sum(v => (v - mean) * (v - mean));
    return Mathf.Sqrt(sumSquares / values.Count);  // N, not N-1
}
```

**Game-1 impact**: The LightGBM feature extractors use `np.std()` (population standard deviation, divides by N). Using sample standard deviation (divides by N-1) will produce different feature values and incorrect model predictions.

### 8.9 Dictionary Iteration Order

```python
# Python 3.7+: dict preserves insertion order (guaranteed)
d = {"b": 2, "a": 1, "c": 3}
list(d.keys())  # ["b", "a", "c"] -- insertion order
```

```csharp
// C#: Dictionary<TKey, TValue> does NOT guarantee order
// Use SortedDictionary<TKey, TValue> for sorted order
// Use OrderedDictionary or List<KeyValuePair<K,V>> for insertion order
var d = new Dictionary<string, int>
{
    ["b"] = 2, ["a"] = 1, ["c"] = 3
};
// Iteration order is NOT guaranteed to match insertion order
```

**Game-1 impact**: The LightGBM feature extractors iterate dictionaries in a specific order to produce feature vectors. Use explicit index counters and sorted keys (or a predefined key order array), never rely on dictionary iteration order.

---

## 9. Quick Reference Card

### Deterministic Random (World Generation)

```csharp
// Use System.Random with explicit seed (NOT UnityEngine.Random)
var rng = new System.Random(seed);
int value = rng.Next(min, max);       // [min, max) exclusive upper
double fraction = rng.NextDouble();    // [0.0, 1.0)
```

### Non-Deterministic Random (Combat)

```csharp
// UnityEngine.Random is fine for combat, drops, crits
float roll = UnityEngine.Random.value;        // [0.0, 1.0]
int count = UnityEngine.Random.Range(1, 4);   // 1, 2, or 3
float damage = UnityEngine.Random.Range(20f, 30f);  // [20.0, 30.0]
```

### Weighted Random Selection

```csharp
// Replacement for Python's random.choices(items, weights)
public static T WeightedChoice<T>(List<T> items, List<float> weights, System.Random rng)
{
    float totalWeight = weights.Sum();
    float roll = (float)rng.NextDouble() * totalWeight;
    float cumulative = 0f;
    for (int i = 0; i < items.Count; i++)
    {
        cumulative += weights[i];
        if (roll <= cumulative)
            return items[i];
    }
    return items[^1];  // Fallback to last item
}
```

### Clamp Pattern

```csharp
// Python: max(min_val, min(max_val, x))
// C#:
float clamped = Mathf.Clamp(x, minVal, maxVal);
int clampedInt = Mathf.Clamp(intVal, minVal, maxVal);
```

### Position & Distance Pattern (3D-Ready)

```csharp
// Python: distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)
// C# (WRONG — hardcodes 2D):
float dist = Mathf.Sqrt((x2-x1)*(x2-x1) + (z2-z1)*(z2-z1));

// C# (RIGHT — uses centralized distance, 3D-ready):
float dist = TargetFinder.GetDistance(posA, posB);
// In Horizontal mode: XZ-plane distance (matches Python)
// In Full3D mode: Vector3.Distance (future)

// Python: Position(x, y)
// C#:
var pos = GamePosition.FromXZ(x, y); // Python y → Unity z, height = 0
```

### Item Type Pattern (IGameItem)

```csharp
// Python: if hasattr(item, 'equipment_data') and item.equipment_data is not None:
// C# (WRONG — string-based type checking):
if (stack.Category == "equipment") { ... }

// C# (RIGHT — pattern matching):
if (stack.Item is EquipmentItem equip)
{
    float effectiveness = equip.GetEffectiveness();
    // equip.Slot, equip.Enchantments, etc.
}
```
