import numpy as np
import tensorflow as tf
from tensorflow import keras
import json
from pathlib import Path
from datetime import datetime
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns


class ComprehensiveModelEvaluator:
    """Comprehensive evaluation of all models on the full dataset"""

    def __init__(self, dataset_path):
        """
        Args:
            dataset_path: Path to adornment_dataset.npz
        """
        self.dataset_path = dataset_path

        # Load dataset
        print("Loading dataset...")
        data = np.load(dataset_path)

        self.X_train = data['X_train']
        self.y_train = data['y_train']
        self.X_val = data['X_val']
        self.y_val = data['y_val']

        print(f"✓ Dataset loaded")
        print(f"  Training: {len(self.X_train)} samples")
        print(f"    Valid: {int(self.y_train.sum())} ({self.y_train.sum() / len(self.y_train) * 100:.1f}%)")
        print(
            f"    Invalid: {int(len(self.y_train) - self.y_train.sum())} ({(len(self.y_train) - self.y_train.sum()) / len(self.y_train) * 100:.1f}%)")
        print(f"  Validation: {len(self.X_val)} samples")
        print(f"    Valid: {int(self.y_val.sum())} ({self.y_val.sum() / len(self.y_val) * 100:.1f}%)")
        print(
            f"    Invalid: {int(len(self.y_val) - self.y_val.sum())} ({(len(self.y_val) - self.y_val.sum()) / len(self.y_val) * 100:.1f}%)\n")

        self.results = []

    def evaluate_model(self, model_path, model_name=None):
        """Evaluate a single model on train and validation sets"""

        if model_name is None:
            model_name = Path(model_path).name

        print(f"\n{'=' * 80}")
        print(f"Evaluating: {model_name}")
        print(f"{'=' * 80}")

        # Load model
        try:
            model = keras.models.load_model(model_path)
        except Exception as e:
            print(f"ERROR loading model: {e}")
            return None

        # Evaluate on training set
        print("\n--- Training Set ---")
        train_metrics = self._evaluate_on_set(model, self.X_train, self.y_train, "Training")

        # Evaluate on validation set
        print("\n--- Validation Set ---")
        val_metrics = self._evaluate_on_set(model, self.X_val, self.y_val, "Validation")

        # Calculate overfitting indicators
        acc_gap = train_metrics['accuracy'] - val_metrics['accuracy']
        f1_gap = train_metrics['f1'] - val_metrics['f1']

        # Determine overfitting level
        if acc_gap < 0.05:
            overfitting_level = "Low"
        elif acc_gap < 0.10:
            overfitting_level = "Medium"
        else:
            overfitting_level = "High"

        print(f"\n--- Overfitting Analysis ---")
        print(f"Accuracy gap (train - val): {acc_gap:.4f}")
        print(f"F1 gap (train - val): {f1_gap:.4f}")
        print(f"Overfitting level: {overfitting_level}")

        # Store results
        result = {
            'model_name': model_name,
            'model_path': str(model_path),
            'model_params': model.count_params(),
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'overfitting': {
                'accuracy_gap': float(acc_gap),
                'f1_gap': float(f1_gap),
                'level': overfitting_level
            }
        }

        # Cleanup
        del model
        tf.keras.backend.clear_session()

        return result

    def _evaluate_on_set(self, model, X, y_true, set_name):
        """Evaluate model on a dataset"""

        # Get predictions
        y_pred_proba = model.predict(X, verbose=0)
        y_pred = (y_pred_proba >= 0.5).astype(int).flatten()

        # Calculate metrics
        accuracy = np.mean(y_pred == y_true)

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        # Calculate metrics manually
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

        # Print metrics
        print(f"Accuracy:    {accuracy:.4f}")
        print(f"Precision:   {precision:.4f} (of predicted valid, how many are actually valid)")
        print(f"Recall:      {recall:.4f} (of actual valid, how many we found)")
        print(f"Specificity: {specificity:.4f} (of actual invalid, how many we found)")
        print(f"F1 Score:    {f1:.4f}")

        print(f"\nConfusion Matrix:")
        print(f"  True Negative:  {tn:4d} (correctly predicted invalid)")
        print(f"  False Positive: {fp:4d} (predicted valid, actually invalid)")
        print(f"  False Negative: {fn:4d} (predicted invalid, actually valid)")
        print(f"  True Positive:  {tp:4d} (correctly predicted valid)")

        return {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'specificity': float(specificity),
            'f1': float(f1),
            'confusion_matrix': {
                'tn': int(tn),
                'fp': int(fp),
                'fn': int(fn),
                'tp': int(tp)
            }
        }

    def evaluate_all_models(self, model_dirs=None):
        """Evaluate all models in specified directories"""

        if model_dirs is None:
            model_dirs = [
                Path("models"),
                Path("smart_search_results"),
                Path("targeted_results"),
                Path("experiment_results")
            ]

        # Find all models
        model_paths = []
        for model_dir in model_dirs:
            if model_dir.exists():
                models = list(model_dir.glob("*.keras"))
                model_paths.extend(models)

        if not model_paths:
            print("No models found!")
            return []

        # Sort by modification time (most recent first)
        model_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        print(f"\n{'=' * 80}")
        print(f"COMPREHENSIVE MODEL EVALUATION")
        print(f"{'=' * 80}")
        print(f"Found {len(model_paths)} models to evaluate")
        print(f"Dataset: {self.dataset_path}")
        print(f"{'=' * 80}")

        # Evaluate each model
        self.results = []
        for i, model_path in enumerate(model_paths, 1):
            print(f"\n{'#' * 80}")
            print(f"MODEL {i}/{len(model_paths)}")
            print(f"{'#' * 80}")

            try:
                result = self.evaluate_model(model_path)
                if result:
                    self.results.append(result)
            except Exception as e:
                print(f"ERROR evaluating {model_path.name}: {e}")
                continue

        # Save and display results
        self._save_results()
        self._print_comparison()

        return self.results

    def _save_results(self):
        """Save evaluation results to JSON"""

        output_dir = Path("comprehensive_evaluation")
        output_dir.mkdir(exist_ok=True)

        # Prepare summary
        summary = {
            'timestamp': datetime.now().isoformat(),
            'dataset_path': str(self.dataset_path),
            'total_models': len(self.results),
            'dataset_info': {
                'train_samples': len(self.X_train),
                'train_valid': int(self.y_train.sum()),
                'train_invalid': int(len(self.y_train) - self.y_train.sum()),
                'val_samples': len(self.X_val),
                'val_valid': int(self.y_val.sum()),
                'val_invalid': int(len(self.y_val) - self.y_val.sum())
            },
            'models': self.results
        }

        # Save full results
        results_file = output_dir / f"evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n✓ Results saved to: {results_file}")

    def _print_comparison(self):
        """Print comparison table of all models"""

        print(f"\n{'=' * 120}")
        print("MODEL COMPARISON - SORTED BY VALIDATION F1 SCORE")
        print(f"{'=' * 120}")

        # Sort by validation F1 score
        sorted_results = sorted(
            self.results,
            key=lambda x: x['val_metrics']['f1'],
            reverse=True
        )

        # Print header
        print(
            f"{'Model':<45} {'Val Acc':>8} {'Val F1':>8} {'Train Acc':>9} {'Overfit':>8} {'Val Prec':>9} {'Val Rec':>8}")
        print(f"{'-' * 120}")

        # Print each model
        for result in sorted_results:
            model_name = result['model_name']
            if len(model_name) > 44:
                model_name = model_name[:41] + "..."

            val_acc = result['val_metrics']['accuracy']
            val_f1 = result['val_metrics']['f1']
            val_prec = result['val_metrics']['precision']
            val_rec = result['val_metrics']['recall']
            train_acc = result['train_metrics']['accuracy']
            acc_gap = result['overfitting']['accuracy_gap']
            overfit_level = result['overfitting']['level']

            # Color code overfitting level
            overfit_str = f"{acc_gap:.4f}"

            print(
                f"{model_name:<45} {val_acc:>8.4f} {val_f1:>8.4f} {train_acc:>9.4f} {overfit_str:>8} {val_prec:>9.4f} {val_rec:>8.4f}")

        print(f"{'=' * 120}")

        # Print top 5 with detailed info
        print(f"\nTOP 5 MODELS (by Validation F1):")
        print(f"{'=' * 120}")

        for i, result in enumerate(sorted_results[:5], 1):
            print(f"\n{i}. {result['model_name']}")
            print(f"   Validation Metrics:")
            print(f"     Accuracy:    {result['val_metrics']['accuracy']:.4f}")
            print(f"     F1 Score:    {result['val_metrics']['f1']:.4f}")
            print(f"     Precision:   {result['val_metrics']['precision']:.4f}")
            print(f"     Recall:      {result['val_metrics']['recall']:.4f}")
            print(f"     Specificity: {result['val_metrics']['specificity']:.4f}")
            print(f"   Training Metrics:")
            print(f"     Accuracy:    {result['train_metrics']['accuracy']:.4f}")
            print(f"     F1 Score:    {result['train_metrics']['f1']:.4f}")
            print(f"   Overfitting:")
            print(f"     Accuracy Gap: {result['overfitting']['accuracy_gap']:.4f}")
            print(f"     Level:        {result['overfitting']['level']}")
            print(f"   Model Params: {result['model_params']:,}")

        print(f"{'=' * 120}")

        # Identify best model
        best_model = sorted_results[0]
        print(f"\n🏆 BEST MODEL: {best_model['model_name']}")
        print(f"   Validation F1: {best_model['val_metrics']['f1']:.4f}")
        print(f"   Validation Accuracy: {best_model['val_metrics']['accuracy']:.4f}")
        print(f"   Overfitting Level: {best_model['overfitting']['level']}")
        print(f"   Path: {best_model['model_path']}")

    def plot_comparison(self, save_path=None):
        """Create visualization comparing models"""

        if not self.results:
            print("No results to plot!")
            return

        # Sort by validation F1
        sorted_results = sorted(
            self.results,
            key=lambda x: x['val_metrics']['f1'],
            reverse=True
        )

        model_names = [r['model_name'][:30] for r in sorted_results]
        val_f1 = [r['val_metrics']['f1'] for r in sorted_results]
        val_acc = [r['val_metrics']['accuracy'] for r in sorted_results]
        train_f1 = [r['train_metrics']['f1'] for r in sorted_results]
        train_acc = [r['train_metrics']['accuracy'] for r in sorted_results]
        overfit_gap = [r['overfitting']['accuracy_gap'] for r in sorted_results]

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # Plot 1: F1 Scores
        x = np.arange(len(model_names))
        width = 0.35
        axes[0, 0].bar(x - width / 2, train_f1, width, label='Train F1', alpha=0.8)
        axes[0, 0].bar(x + width / 2, val_f1, width, label='Val F1', alpha=0.8)
        axes[0, 0].set_xlabel('Model')
        axes[0, 0].set_ylabel('F1 Score')
        axes[0, 0].set_title('F1 Score Comparison')
        axes[0, 0].set_xticks(x)
        axes[0, 0].set_xticklabels(model_names, rotation=45, ha='right')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        # Plot 2: Accuracy
        axes[0, 1].bar(x - width / 2, train_acc, width, label='Train Acc', alpha=0.8)
        axes[0, 1].bar(x + width / 2, val_acc, width, label='Val Acc', alpha=0.8)
        axes[0, 1].set_xlabel('Model')
        axes[0, 1].set_ylabel('Accuracy')
        axes[0, 1].set_title('Accuracy Comparison')
        axes[0, 1].set_xticks(x)
        axes[0, 1].set_xticklabels(model_names, rotation=45, ha='right')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)

        # Plot 3: Overfitting Gap
        colors = ['green' if gap < 0.05 else 'orange' if gap < 0.10 else 'red' for gap in overfit_gap]
        axes[1, 0].bar(x, overfit_gap, color=colors, alpha=0.7)
        axes[1, 0].axhline(y=0.05, color='orange', linestyle='--', label='Medium threshold')
        axes[1, 0].axhline(y=0.10, color='red', linestyle='--', label='High threshold')
        axes[1, 0].set_xlabel('Model')
        axes[1, 0].set_ylabel('Accuracy Gap (Train - Val)')
        axes[1, 0].set_title('Overfitting Analysis')
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(model_names, rotation=45, ha='right')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

        # Plot 4: Precision vs Recall (scatter)
        val_prec = [r['val_metrics']['precision'] for r in sorted_results]
        val_rec = [r['val_metrics']['recall'] for r in sorted_results]

        axes[1, 1].scatter(val_rec, val_prec, s=100, alpha=0.6)
        for i, name in enumerate(model_names):
            axes[1, 1].annotate(f"{i + 1}", (val_rec[i], val_prec[i]),
                                textcoords="offset points", xytext=(5, 5), ha='center')
        axes[1, 1].set_xlabel('Recall (Validation)')
        axes[1, 1].set_ylabel('Precision (Validation)')
        axes[1, 1].set_title('Precision vs Recall Trade-off')
        axes[1, 1].grid(True, alpha=0.3)
        axes[1, 1].set_xlim([0, 1.05])
        axes[1, 1].set_ylim([0, 1.05])

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ Plot saved to: {save_path}")

        plt.show()


# Example usage
if __name__ == "__main__":
    import sys

    # Get dataset path
    dataset_path = "adornment_dataset.npz"

    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    elif not Path(dataset_path).exists():
        dataset_path = input("Enter path to adornment_dataset.npz: ").strip()

    if not Path(dataset_path).exists():
        print(f"Error: Dataset not found at {dataset_path}")
        sys.exit(1)

    # Create evaluator
    evaluator = ComprehensiveModelEvaluator(dataset_path)

    # Evaluate all models
    results = evaluator.evaluate_all_models()

    # Create visualization
    if results:
        plot_path = "comprehensive_evaluation/model_comparison.png"
        evaluator.plot_comparison(save_path=plot_path)

    print("\n✓ Comprehensive evaluation complete!")