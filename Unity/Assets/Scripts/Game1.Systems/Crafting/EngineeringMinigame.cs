// ============================================================================
// Game1.Systems.Crafting.EngineeringMinigame
// Migrated from: Crafting-subdisciplines/engineering.py (1315 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Engineering minigame: Sequential cognitive puzzle solving.
//
// Two puzzle types:
// 1. RotationPipePuzzle: Rotate pipe pieces to connect input to output (BFS path check)
// 2. LogicSwitchPuzzle: Lights-out style toggle puzzle (click toggles cell + neighbors)
//
// All recipes get at least 2 puzzles: index 0 = RotationPipe, index 1+ = LogicSwitch.
//
// Performance:
//   base = completion_ratio * 0.5 + avg_efficiency * 0.3
//   time_bonus = time_ratio * 0.2 (if all solved before time)
//   hint_penalty = hints_used * 0.05
//   first_try_bonus = +0.05
//
// No hard failure: if time expires, auto-completes with partial progress.
//

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Crafting
{
    // =========================================================================
    // Puzzle Interfaces / Base
    // =========================================================================

    /// <summary>
    /// Common interface for engineering puzzles.
    /// </summary>
    public interface IEngineeringPuzzle
    {
        string PuzzleType { get; }
        bool CheckSolution();
        float GetEfficiencyScore();
        void Reset();
        Dictionary<string, object> GetState();
    }

    // =========================================================================
    // Rotation Pipe Puzzle
    // =========================================================================

    /// <summary>
    /// Rotate pipe pieces to form a path from input to output.
    /// Piece types: 0=empty, 1=straight, 2=L-bend, 3=T-junction, 4=cross.
    /// </summary>
    public class RotationPipePuzzle : IEngineeringPuzzle
    {
        // Connection maps: for each piece type, which sides connect at each rotation
        // Sides: 0=top, 1=right, 2=bottom, 3=left
        private static readonly Dictionary<int, Dictionary<int, int[]>> Connections = new()
        {
            [0] = new() { [0] = Array.Empty<int>(), [90] = Array.Empty<int>(), [180] = Array.Empty<int>(), [270] = Array.Empty<int>() },
            [1] = new() { [0] = new[] { 1, 3 }, [90] = new[] { 0, 2 }, [180] = new[] { 1, 3 }, [270] = new[] { 0, 2 } },
            [2] = new() { [0] = new[] { 0, 1 }, [90] = new[] { 1, 2 }, [180] = new[] { 2, 3 }, [270] = new[] { 3, 0 } },
            [3] = new() { [0] = new[] { 0, 1, 3 }, [90] = new[] { 0, 1, 2 }, [180] = new[] { 1, 2, 3 }, [270] = new[] { 0, 2, 3 } },
            [4] = new() { [0] = new[] { 0, 1, 2, 3 }, [90] = new[] { 0, 1, 2, 3 }, [180] = new[] { 0, 1, 2, 3 }, [270] = new[] { 0, 1, 2, 3 } }
        };

        public string PuzzleType => "rotation_pipe";

        public int GridSize { get; }
        public int[,] Grid { get; private set; }
        public int[,] Rotations { get; private set; }
        public (int Row, int Col) InputPos { get; }
        public (int Row, int Col) OutputPos { get; }
        public int Clicks { get; private set; }
        public int IdealPathLength { get; private set; }
        public int ActualPathLength { get; private set; }

        private int[,] _solutionRotations;
        private Random _rng;

        public RotationPipePuzzle(int gridSize = 3, string difficulty = "easy", Random rng = null)
        {
            GridSize = gridSize;
            _rng = rng ?? new Random();
            InputPos = (0, _rng.Next(gridSize));
            OutputPos = (gridSize - 1, _rng.Next(gridSize));
            GeneratePuzzle();
        }

        private void GeneratePuzzle()
        {
            Grid = new int[GridSize, GridSize];
            Rotations = new int[GridSize, GridSize];

            // Calculate ideal path length
            IdealPathLength = Math.Abs(OutputPos.Row - InputPos.Row)
                            + Math.Abs(OutputPos.Col - InputPos.Col) + 1;

            // Build winding path from input to output
            var path = new List<(int R, int C)>();
            var visited = new HashSet<(int, int)>();
            var current = InputPos;
            path.Add(current);
            visited.Add(current);

            int[] dr = { 0, 1, 0, -1 };
            int[] dc = { 1, 0, -1, 0 };

            while (current != OutputPos)
            {
                var neighbors = new List<((int R, int C) Pos, int Dist)>();
                for (int d = 0; d < 4; d++)
                {
                    int nr = current.Row + dr[d];
                    int nc = current.Col + dc[d];
                    if (nr >= 0 && nr < GridSize && nc >= 0 && nc < GridSize && !visited.Contains((nr, nc)))
                    {
                        int dist = Math.Abs(nr - OutputPos.Row) + Math.Abs(nc - OutputPos.Col);
                        neighbors.Add(((nr, nc), dist));
                    }
                }

                if (neighbors.Count == 0)
                {
                    if (path.Count > 1)
                    {
                        path.RemoveAt(path.Count - 1);
                        current = path[^1];
                        continue;
                    }
                    break;
                }

                neighbors.Sort((a, b) => a.Dist.CompareTo(b.Dist));
                var next = _rng.NextDouble() < 0.7 ? neighbors[0].Pos : neighbors[_rng.Next(neighbors.Count)].Pos;
                current = next;
                path.Add(current);
                visited.Add(current);
            }

            ActualPathLength = path.Count;

            // Convert path to pipe pieces
            for (int i = 0; i < path.Count; i++)
            {
                var (r, c) = path[i];
                if (i == 0)
                {
                    var (nr, nc) = path[i + 1];
                    (Grid[r, c], Rotations[r, c]) = GetPieceForConnection(r, c, nr, nc);
                }
                else if (i == path.Count - 1)
                {
                    var (pr, pc) = path[i - 1];
                    (Grid[r, c], Rotations[r, c]) = GetPieceForConnection(r, c, pr, pc);
                }
                else
                {
                    var (pr, pc) = path[i - 1];
                    var (nr, nc) = path[i + 1];
                    (Grid[r, c], Rotations[r, c]) = GetPieceForTwoConnections(r, c, pr, pc, nr, nc);
                }
            }

            // Fill empty cells with random pipes (distractors)
            int[] distTypes = { 1, 2, 2, 3 };
            int[] distRots = { 0, 90, 180, 270 };
            for (int r = 0; r < GridSize; r++)
            {
                for (int c = 0; c < GridSize; c++)
                {
                    if (Grid[r, c] == 0)
                    {
                        Grid[r, c] = distTypes[_rng.Next(distTypes.Length)];
                        Rotations[r, c] = distRots[_rng.Next(distRots.Length)];
                    }
                }
            }

            // Save solution
            _solutionRotations = (int[,])Rotations.Clone();

            // Scramble all pieces
            for (int r = 0; r < GridSize; r++)
            {
                for (int c = 0; c < GridSize; c++)
                {
                    if (Grid[r, c] != 0 && Grid[r, c] != 4)
                        Rotations[r, c] = distRots[_rng.Next(distRots.Length)];
                }
            }
        }

        private (int Type, int Rotation) GetPieceForConnection(int r, int c, int tr, int tc)
        {
            if (tr < r || tr > r) return (1, 90); // vertical straight
            return (1, 0); // horizontal straight
        }

        private (int Type, int Rotation) GetPieceForTwoConnections(int r, int c, int pr, int pc, int nr, int nc)
        {
            var dirs = new HashSet<int>();
            if (pr < r || nr < r) dirs.Add(0);
            if (pc > c || nc > c) dirs.Add(1);
            if (pr > r || nr > r) dirs.Add(2);
            if (pc < c || nc < c) dirs.Add(3);

            // Straight line
            if (dirs.SetEquals(new[] { 0, 2 }) || dirs.SetEquals(new[] { 1, 3 }))
                return (1, dirs.Contains(0) ? 90 : 0);

            // L-bend: find correct rotation
            foreach (int rot in new[] { 0, 90, 180, 270 })
            {
                var conn = new HashSet<int>(Connections[2][rot]);
                if (conn.SetEquals(dirs))
                    return (2, rot);
            }

            return (2, 0); // Fallback
        }

        /// <summary>Rotate piece at (row, col) clockwise 90 degrees.</summary>
        public bool RotatePiece(int row, int col)
        {
            if (row < 0 || row >= GridSize || col < 0 || col >= GridSize) return false;
            if (Grid[row, col] == 0 || Grid[row, col] == 4) return false;

            Rotations[row, col] = (Rotations[row, col] + 90) % 360;
            Clicks++;
            return true;
        }

        /// <summary>BFS path check: can we get from input to output through connected pipes?</summary>
        public bool CheckSolution()
        {
            var visited = new HashSet<(int, int)>();
            var queue = new Queue<(int, int)>();
            queue.Enqueue(InputPos);
            visited.Add(InputPos);

            int[] dRow = { -1, 0, 1, 0 };
            int[] dCol = { 0, 1, 0, -1 };
            int[] opposite = { 2, 3, 0, 1 };

            while (queue.Count > 0)
            {
                var (r, c) = queue.Dequeue();

                if ((r, c) == OutputPos) return true;

                int pieceType = Grid[r, c];
                if (pieceType == 0) continue;

                int rotation = Rotations[r, c];
                int[] connections = Connections[pieceType][rotation];

                foreach (int side in connections)
                {
                    int nr = r + dRow[side];
                    int nc = c + dCol[side];

                    if (nr < 0 || nr >= GridSize || nc < 0 || nc >= GridSize) continue;
                    if (visited.Contains((nr, nc))) continue;

                    int neighborType = Grid[nr, nc];
                    if (neighborType == 0) continue;

                    int neighborRot = Rotations[nr, nc];
                    int[] neighborConn = Connections[neighborType][neighborRot];

                    // Check if neighbor connects back to us
                    if (Array.IndexOf(neighborConn, opposite[side]) >= 0)
                    {
                        visited.Add((nr, nc));
                        queue.Enqueue((nr, nc));
                    }
                }
            }

            return false;
        }

        /// <summary>Efficiency: ideal_path_length / actual_path_length, capped at 1.0.</summary>
        public float GetEfficiencyScore()
        {
            if (ActualPathLength == 0) return 1.0f;
            return Math.Min(1.0f, (float)IdealPathLength / ActualPathLength);
        }

        public void Reset()
        {
            // Re-scramble all pieces
            int[] rots = { 0, 90, 180, 270 };
            for (int r = 0; r < GridSize; r++)
                for (int c = 0; c < GridSize; c++)
                    if (Grid[r, c] != 0 && Grid[r, c] != 4)
                        Rotations[r, c] = rots[_rng.Next(rots.Length)];
            Clicks = 0;
        }

        public Dictionary<string, object> GetState()
        {
            return new Dictionary<string, object>
            {
                ["puzzle_type"] = PuzzleType,
                ["grid_size"] = GridSize,
                ["input_pos"] = new[] { InputPos.Row, InputPos.Col },
                ["output_pos"] = new[] { OutputPos.Row, OutputPos.Col },
                ["clicks"] = Clicks,
                ["solved"] = CheckSolution(),
                ["efficiency"] = GetEfficiencyScore()
            };
        }
    }

    // =========================================================================
    // Logic Switch Puzzle (Lights-Out style)
    // =========================================================================

    /// <summary>
    /// Toggle switches to match target pattern. Clicking toggles cell + orthogonal neighbors.
    /// Scoring: moves vs ideal (exponential decay: e^-(moves/ideal - 1)).
    /// </summary>
    public class LogicSwitchPuzzle : IEngineeringPuzzle
    {
        public string PuzzleType => "logic_switch";
        public string PuzzleMode { get; private set; }

        public int GridSize { get; }
        public int[,] Grid { get; private set; }
        public int[,] Target { get; private set; }
        public int[,] InitialGrid { get; private set; }
        public int Moves { get; private set; }
        public int IdealMoves { get; private set; }

        private List<(int R, int C)> _solutionPath = new();
        private Random _rng;

        public LogicSwitchPuzzle(int gridSize = 3, string difficulty = "easy", int maxMoves = 10, string forceMode = null, Random rng = null)
        {
            GridSize = gridSize;
            _rng = rng ?? new Random();
            GeneratePuzzle(difficulty, maxMoves, forceMode);
        }

        private void GeneratePuzzle(string difficulty, int maxMoves, string forceMode)
        {
            string mode;
            if (forceMode != null)
            {
                mode = forceMode;
            }
            else if (difficulty == "easy")
            {
                mode = _rng.Next(2) == 0 ? "random_to_lit" : "random_to_dim";
            }
            else if (difficulty == "medium")
            {
                mode = _rng.Next(2) == 0 ? "dim_to_random" : "lit_to_random";
            }
            else // hard
            {
                mode = "lit_to_random";
            }

            switch (mode)
            {
                case "random_to_lit":
                    PuzzleMode = "random -> fully_lit";
                    GenerateForward(1, maxMoves);
                    break;
                case "random_to_dim":
                    PuzzleMode = "random -> fully_dim";
                    GenerateForward(0, maxMoves);
                    break;
                case "dim_to_random":
                    PuzzleMode = "fully_dim -> random";
                    GenerateReversed(0, maxMoves);
                    break;
                case "lit_to_random":
                    PuzzleMode = "fully_lit -> random";
                    GenerateReversed(1, maxMoves);
                    break;
            }
        }

        private void GenerateForward(int targetState, int numToggles)
        {
            Target = new int[GridSize, GridSize];
            Grid = new int[GridSize, GridSize];
            for (int r = 0; r < GridSize; r++)
                for (int c = 0; c < GridSize; c++)
                {
                    Target[r, c] = targetState;
                    Grid[r, c] = targetState;
                }

            _solutionPath = new List<(int, int)>();
            var cellsUsed = new HashSet<(int, int)>();

            for (int i = 0; i < numToggles; i++)
            {
                var available = GetAvailableCells(cellsUsed);
                if (available.Count == 0)
                {
                    cellsUsed.Clear();
                    available = GetAvailableCells(cellsUsed);
                }

                var cell = available[_rng.Next(available.Count)];
                cellsUsed.Add(cell);
                _solutionPath.Add(cell);
                DoToggle(Grid, cell.R, cell.C);
            }

            IdealMoves = _solutionPath.Count;
            Moves = 0;
            InitialGrid = (int[,])Grid.Clone();
        }

        private void GenerateReversed(int startState, int numToggles)
        {
            Grid = new int[GridSize, GridSize];
            Target = new int[GridSize, GridSize];
            for (int r = 0; r < GridSize; r++)
                for (int c = 0; c < GridSize; c++)
                {
                    Grid[r, c] = startState;
                    Target[r, c] = startState;
                }

            _solutionPath = new List<(int, int)>();
            var cellsUsed = new HashSet<(int, int)>();

            for (int i = 0; i < numToggles; i++)
            {
                var available = GetAvailableCells(cellsUsed);
                if (available.Count == 0)
                {
                    cellsUsed.Clear();
                    available = GetAvailableCells(cellsUsed);
                }

                var cell = available[_rng.Next(available.Count)];
                cellsUsed.Add(cell);
                _solutionPath.Add(cell);
                DoToggle(Target, cell.R, cell.C);
            }

            IdealMoves = _solutionPath.Count;
            Moves = 0;
            InitialGrid = (int[,])Grid.Clone();
        }

        private List<(int R, int C)> GetAvailableCells(HashSet<(int, int)> used)
        {
            var list = new List<(int R, int C)>();
            for (int r = 0; r < GridSize; r++)
                for (int c = 0; c < GridSize; c++)
                    if (!used.Contains((r, c)))
                        list.Add((r, c));
            return list;
        }

        private static void DoToggle(int[,] grid, int row, int col)
        {
            int size = grid.GetLength(0);
            grid[row, col] = 1 - grid[row, col];
            int[] dr = { -1, 1, 0, 0 };
            int[] dc = { 0, 0, -1, 1 };
            for (int d = 0; d < 4; d++)
            {
                int nr = row + dr[d];
                int nc = col + dc[d];
                if (nr >= 0 && nr < size && nc >= 0 && nc < size)
                    grid[nr, nc] = 1 - grid[nr, nc];
            }
        }

        /// <summary>Toggle switch at position (player action).</summary>
        public bool ToggleSwitch(int row, int col)
        {
            if (row < 0 || row >= GridSize || col < 0 || col >= GridSize) return false;
            DoToggle(Grid, row, col);
            Moves++;
            return true;
        }

        public bool CheckSolution()
        {
            for (int r = 0; r < GridSize; r++)
                for (int c = 0; c < GridSize; c++)
                    if (Grid[r, c] != Target[r, c])
                        return false;
            return true;
        }

        /// <summary>
        /// Efficiency based on moves vs ideal.
        /// Perfect (ideal moves) = 1.0.
        /// More moves = exponential decay: e^-(ratio - 1).
        /// </summary>
        public float GetEfficiencyScore()
        {
            if (IdealMoves == 0) return 1.0f;
            float ratio = (float)Moves / IdealMoves;
            if (ratio <= 1.0f) return 1.0f;
            return (float)Math.Exp(-(ratio - 1.0));
        }

        public void Reset()
        {
            Grid = (int[,])InitialGrid.Clone();
            Moves = 0;
        }

        public Dictionary<string, object> GetState()
        {
            return new Dictionary<string, object>
            {
                ["puzzle_type"] = PuzzleType,
                ["puzzle_mode"] = PuzzleMode,
                ["grid_size"] = GridSize,
                ["moves"] = Moves,
                ["ideal_moves"] = IdealMoves,
                ["efficiency"] = GetEfficiencyScore(),
                ["solved"] = CheckSolution()
            };
        }
    }

    // =========================================================================
    // Engineering Minigame
    // =========================================================================

    /// <summary>
    /// Engineering crafting minigame. Extends BaseCraftingMinigame.
    /// Sequential puzzle solving (rotation pipes + logic switches).
    /// </summary>
    public class EngineeringMinigame : BaseCraftingMinigame
    {
        // =====================================================================
        // State
        // =====================================================================

        private int _puzzleCount;
        private int _gridSize;
        private int _complexity;
        private int _hintsAllowed;
        private int _hintsUsed;
        private int _idealMoves;

        private List<IEngineeringPuzzle> _puzzles = new();
        private int _currentPuzzleIndex;
        private List<IEngineeringPuzzle> _solvedPuzzles = new();
        private List<float> _puzzleEfficiencies = new();
        private bool _timeExpired;

        // =====================================================================
        // Properties
        // =====================================================================

        public int PuzzleCount => _puzzleCount;
        public int CurrentPuzzleIndex => _currentPuzzleIndex;
        public int SolvedCount => _solvedPuzzles.Count;
        public IEngineeringPuzzle CurrentPuzzle =>
            _currentPuzzleIndex < _puzzles.Count ? _puzzles[_currentPuzzleIndex] : null;
        public IReadOnlyList<float> PuzzleEfficiencies => _puzzleEfficiencies;
        public int HintsUsed => _hintsUsed;

        // =====================================================================
        // Constructor
        // =====================================================================

        public EngineeringMinigame(
            List<RecipeInput> inputs,
            Dictionary<string, object> recipeMeta = null,
            float buffTimeBonus = 0f,
            float buffQualityBonus = 0f,
            int intStat = 0,
            int? seed = null)
            : base(inputs, recipeMeta, buffTimeBonus, buffQualityBonus, seed)
        {
            var p = DifficultyCalculator.GetEngineeringParams(
                inputs, GetStationTier(), intStat);

            _difficultyPoints = p.DifficultyPoints;
            _difficultyTier = p.DifficultyTier;

            _puzzleCount = Math.Max(2, p.PuzzleCount); // Always at least 2
            _gridSize = p.GridSize;
            _complexity = p.Complexity;
            _hintsAllowed = p.HintsAllowed;
            _idealMoves = p.IdealMoves;

            float baseTime = p.TimeLimit;
            // Apply speed bonus to extend time limit
            if (buffTimeBonus > 0)
                baseTime = (int)(baseTime * (1.0f + buffTimeBonus));

            _totalTime = baseTime;
            _timeRemaining = baseTime;
        }

        // =====================================================================
        // BaseCraftingMinigame Implementation
        // =====================================================================

        protected override void InitializeMinigame()
        {
            _currentPuzzleIndex = 0;
            _solvedPuzzles = new List<IEngineeringPuzzle>();
            _puzzleEfficiencies = new List<float>();
            _hintsUsed = 0;
            _timeExpired = false;
            _timeRemaining = _totalTime;

            // Generate puzzles: index 0 = RotationPipe, index 1+ = LogicSwitch
            _puzzles = new List<IEngineeringPuzzle>();
            for (int i = 0; i < _puzzleCount; i++)
            {
                _puzzles.Add(CreatePuzzleForTier(i));
            }
        }

        protected override void UpdateMinigame(float deltaTime)
        {
            // Engineering puzzles are event-driven (no per-frame logic needed)
        }

        protected override void OnTimeExpired()
        {
            // Time expired: auto-complete with current progress (NOT hard fail)
            _timeExpired = true;
            Complete();
        }

        public override bool HandleInput(MinigameInput input)
        {
            if (!IsActive || _currentPuzzleIndex >= _puzzles.Count)
                return false;

            var puzzle = _puzzles[_currentPuzzleIndex];

            switch (input.Type)
            {
                case MinigameInputType.Rotate:
                    if (puzzle is RotationPipePuzzle pipePuzzle)
                        return pipePuzzle.RotatePiece(input.Index, input.Index2);
                    return false;

                case MinigameInputType.Click:
                    if (puzzle is LogicSwitchPuzzle switchPuzzle)
                        return switchPuzzle.ToggleSwitch(input.Index, input.Index2);
                    if (puzzle is RotationPipePuzzle pipePuzzle2)
                        return pipePuzzle2.RotatePiece(input.Index, input.Index2);
                    return false;

                case MinigameInputType.Confirm:
                    // Check solution and advance if solved
                    return CheckCurrentPuzzle();

                case MinigameInputType.Cancel:
                    // Reset current puzzle
                    puzzle.Reset();
                    return true;

                default:
                    return false;
            }
        }

        protected override float CalculatePerformance()
        {
            int puzzlesSolved = _solvedPuzzles.Count;
            float completionRatio = (float)puzzlesSolved / Math.Max(1, _puzzleCount);

            // Average efficiency
            float avgEfficiency = 1.0f;
            if (_puzzleEfficiencies.Count > 0)
            {
                avgEfficiency = 0f;
                foreach (var e in _puzzleEfficiencies) avgEfficiency += e;
                avgEfficiency /= _puzzleEfficiencies.Count;
            }

            // Time ratio
            float timeRatio = _timeRemaining / Math.Max(1f, _totalTime);

            // Performance: completion 50%, efficiency 30%, time 20%
            float basePerformance = completionRatio * 0.5f + avgEfficiency * 0.3f;

            if (!_timeExpired && puzzlesSolved == _puzzleCount)
                basePerformance += timeRatio * 0.2f;
            else if (puzzlesSolved == _puzzleCount)
                basePerformance += 0.1f;

            // Hint penalty
            float hintPenalty = _hintsUsed * 0.05f;
            basePerformance = Math.Max(0f, basePerformance - hintPenalty);

            // First-try bonus
            if (_attempt == 1)
                basePerformance = Math.Min(1.0f, basePerformance + 0.05f);

            return Math.Clamp(basePerformance, 0f, 1f);
        }

        protected override CraftingReward CalculateRewardForDiscipline()
        {
            float timeRatio = _timeRemaining / Math.Max(1f, _totalTime);

            var perf = new EngineeringPerformance
            {
                PuzzlesSolved = _solvedPuzzles.Count,
                TotalPuzzles = _puzzleCount,
                HintsUsed = _hintsUsed,
                TimeRemaining = timeRatio,
                Attempt = _attempt
            };

            return RewardCalculator.CalculateEngineeringRewards(_difficultyPoints, perf);
        }

        protected override Dictionary<string, object> GetDisciplineState()
        {
            Dictionary<string, object> currentPuzzleState = null;
            if (_currentPuzzleIndex < _puzzles.Count)
                currentPuzzleState = _puzzles[_currentPuzzleIndex].GetState();

            return new Dictionary<string, object>
            {
                ["current_puzzle_index"] = _currentPuzzleIndex,
                ["total_puzzles"] = _puzzleCount,
                ["solved_count"] = _solvedPuzzles.Count,
                ["current_puzzle"] = currentPuzzleState,
                ["time_expired"] = _timeExpired,
                ["efficiency_scores"] = new List<float>(_puzzleEfficiencies),
                ["hints_used"] = _hintsUsed,
                ["hints_allowed"] = _hintsAllowed
            };
        }

        // =====================================================================
        // Engineering-Specific Methods
        // =====================================================================

        /// <summary>
        /// Create appropriate puzzle based on difficulty tier.
        /// Index 0: RotationPipePuzzle, Index 1+: LogicSwitchPuzzle.
        /// </summary>
        private IEngineeringPuzzle CreatePuzzleForTier(int index)
        {
            string diff;
            switch (_difficultyTier)
            {
                case "common":
                case "uncommon":
                    diff = index == 0 ? (_difficultyTier == "common" ? "easy" : "medium") : "easy";
                    break;
                case "rare":
                    diff = index == 0 ? "medium" : "easy";
                    break;
                case "epic":
                    diff = index == 0 ? "hard" : "medium";
                    break;
                default: // legendary
                    diff = index == 0 ? "hard" : "hard";
                    break;
            }

            if (index == 0)
                return new RotationPipePuzzle(_gridSize, diff, _rng);
            else
                return new LogicSwitchPuzzle(_gridSize, diff, _idealMoves, rng: _rng);
        }

        /// <summary>
        /// Check if current puzzle is solved. If so, record efficiency and advance.
        /// Returns true if puzzle was solved.
        /// </summary>
        public bool CheckCurrentPuzzle()
        {
            if (_currentPuzzleIndex >= _puzzles.Count) return false;

            var puzzle = _puzzles[_currentPuzzleIndex];

            if (puzzle.CheckSolution())
            {
                _solvedPuzzles.Add(puzzle);
                _puzzleEfficiencies.Add(puzzle.GetEfficiencyScore());

                _currentPuzzleIndex++;

                if (_currentPuzzleIndex >= _puzzles.Count)
                    Complete();

                return true;
            }

            return false;
        }

        /// <summary>
        /// Reset the current puzzle to its initial state.
        /// </summary>
        public void ResetCurrentPuzzle()
        {
            if (_currentPuzzleIndex < _puzzles.Count)
                _puzzles[_currentPuzzleIndex].Reset();
        }

        /// <summary>
        /// Use a hint (if available). Increments hint counter.
        /// Returns true if hint was consumed.
        /// </summary>
        public bool UseHint()
        {
            if (_hintsUsed >= _hintsAllowed) return false;
            _hintsUsed++;
            return true;
        }

        /// <summary>Abandon device creation. Returns 50% materials by convention.</summary>
        public void Abandon()
        {
            Fail();
        }
    }
}
