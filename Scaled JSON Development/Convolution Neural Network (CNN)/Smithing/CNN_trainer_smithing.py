"""
Recipe Validator CNN - Round 2 Hyperparameter Search
Clean implementation with proper data handling and architectures
"""

import numpy as np
import os
import tensorflow as tf
import time
import json
from datetime import datetime
from pathlib import Path

# Use TensorFlow's Keras (what worked in Round 1)
# DO NOT import keras directly - it has circular import bugs


def load_recipe_data(data_path='recipe_dataset.npz'):
    """Load recipe dataset from .npz file

    Expected data format:
    - X_train, X_val: shape (n_samples, 36, 36, 3) - RGB images
    - y_train, y_val: shape (n_samples,) - binary labels
    """
    print(f"Loading dataset from: {data_path}")

    if not Path(data_path).exists():
        raise FileNotFoundError(
            f"Dataset not found: {data_path}\n"
            f"Please ensure the data file exists in the current directory."
        )

    data = np.load(data_path)
    X_train = data['X_train'].astype(np.float32)
    y_train = data['y_train'].astype(np.float32)
    X_val = data['X_val'].astype(np.float32)
    y_val = data['y_val'].astype(np.float32)

    print(f"[OK] Dataset loaded successfully")
    print(f"  Train samples: {len(X_train)}")
    print(f"  Val samples:   {len(X_val)}")
    print(f"  Input shape:   {X_train.shape[1:]}")
    print(f"  Data type:     {X_train.dtype}")

    # Data diagnostics - help debug impossible metrics issues
    print(f"\n=== DATA DIAGNOSTICS ===")
    train_pos = np.sum(y_train == 1)
    train_neg = np.sum(y_train == 0)
    val_pos = np.sum(y_val == 1)
    val_neg = np.sum(y_val == 0)
    print(f"Train: {train_pos} positive ({train_pos/len(y_train)*100:.1f}%), {train_neg} negative ({train_neg/len(y_train)*100:.1f}%)")
    print(f"Val:   {val_pos} positive ({val_pos/len(y_val)*100:.1f}%), {val_neg} negative ({val_neg/len(y_val)*100:.1f}%)")
    print(f"Value range: [{X_train.min():.3f}, {X_train.max():.3f}]")

    # Check for data issues
    if abs(train_pos/len(y_train) - val_pos/len(y_val)) > 0.15:
        print(f"[WARNING] Train/Val class balance differs by more than 15%!")
    if X_train.max() > 1.0 or X_train.min() < 0.0:
        print(f"[WARNING] Data not normalized to [0,1] range!")
    print(f"========================")

    # Validate shape
    if len(X_train.shape) != 4:
        raise ValueError(
            f"Expected 4D data (batch, height, width, channels), "
            f"but got shape {X_train.shape}"
        )

    return X_train, y_train, X_val, y_val


class RecipeValidatorModels:
    """CNN architectures for recipe validation (36×36×3 RGB images)"""

    @staticmethod
    def config_3_wider(input_shape, l2_reg=0.0, dropout_rates=(0.3, 0.4, 0.5)):
        """
        Wider architecture - Round 1 Winner (76.79% val acc)
        ~421K parameters
        """
        reg = tf.keras.regularizers.l2(l2_reg) if l2_reg > 0 else None

        model = tf.keras.Sequential([
            # Input
            tf.keras.layers.Input(shape=input_shape),

            # First conv block
            tf.keras.layers.Conv2D(32, (3, 3), padding='same', activation='relu',
                         kernel_regularizer=reg),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(dropout_rates[0]),

            # Second conv block
            tf.keras.layers.Conv2D(64, (3, 3), padding='same', activation='relu',
                         kernel_regularizer=reg),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(dropout_rates[1]),

            # Third conv block
            tf.keras.layers.Conv2D(128, (3, 3), padding='same', activation='relu',
                         kernel_regularizer=reg),
            tf.keras.layers.MaxPooling2D((2, 2)),

            # Dense layers
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(128, activation='relu', kernel_regularizer=reg),
            tf.keras.layers.Dropout(dropout_rates[2]),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])

        return model

    @staticmethod
    def config_4_minimal(input_shape, l2_reg=0.0, dropout_rates=(0.3, 0.4)):
        """
        Minimal architecture - Round 1 BEST (77.22% val acc)
        ~132K parameters
        """
        reg = tf.keras.regularizers.l2(l2_reg) if l2_reg > 0 else None

        model = tf.keras.Sequential([
            # Input
            tf.keras.layers.Input(shape=input_shape),

            # First conv block
            tf.keras.layers.Conv2D(16, (5, 5), padding='same', activation='relu',
                         kernel_regularizer=reg),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(dropout_rates[0]),

            # Dense layers
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(32, activation='relu', kernel_regularizer=reg),
            tf.keras.layers.Dropout(dropout_rates[1]),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])

        return model

    @staticmethod
    def config_5_medium(input_shape, l2_reg=0.0, dropout_rates=(0.3, 0.4, 0.4)):
        """
        Medium-width architecture (between minimal and wider)
        Target: ~200-250K parameters
        """
        reg = tf.keras.regularizers.l2(l2_reg) if l2_reg > 0 else None

        model = tf.keras.Sequential([
            # Input
            tf.keras.layers.Input(shape=input_shape),

            # First conv block
            tf.keras.layers.Conv2D(24, (3, 3), padding='same', activation='relu',
                         kernel_regularizer=reg),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(dropout_rates[0]),

            # Second conv block
            tf.keras.layers.Conv2D(48, (3, 3), padding='same', activation='relu',
                         kernel_regularizer=reg),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(dropout_rates[1]),

            # Dense layers
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(64, activation='relu', kernel_regularizer=reg),
            tf.keras.layers.Dropout(dropout_rates[2]),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])

        return model


class HyperparameterSearch:
    """Hyperparameter search with proper error handling"""

    def __init__(self, X_train, y_train, X_val, y_val):
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.input_shape = X_train.shape[1:]
        self.results = []

    def build_model(self, config):
        """Build model from configuration with error handling"""
        arch = config['architecture']
        l2_reg = config.get('l2_reg', 0.0)
        dropout_rates = config.get('dropout_rates', (0.3, 0.4, 0.5))

        try:
            if arch == 'config_3':
                model = RecipeValidatorModels.config_3_wider(
                    self.input_shape, l2_reg, dropout_rates
                )
            elif arch == 'config_4':
                model = RecipeValidatorModels.config_4_minimal(
                    self.input_shape, l2_reg, dropout_rates[:2]
                )
            elif arch == 'config_5':
                model = RecipeValidatorModels.config_5_medium(
                    self.input_shape, l2_reg, dropout_rates
                )
            else:
                raise ValueError(f"Unknown architecture: {arch}")

            return model

        except Exception as e:
            print(f"ERROR building model: {e}")
            raise

    def train_single_config(self, config):
        """Train and evaluate a single configuration"""
        name = config['name']

        print(f"\n{'='*80}")
        print(f"Training: {name}")
        print(f"{'='*80}")
        print(f"Architecture:    {config['architecture']}")
        print(f"Learning Rate:   {config['learning_rate']}")
        print(f"Batch Size:      {config['batch_size']}")
        if config.get('l2_reg', 0) > 0:
            print(f"L2 Regularization: {config['l2_reg']}")
        if config.get('use_lr_schedule'):
            print(f"LR Scheduling:   Enabled")

        try:
            # Build model
            model = self.build_model(config)

            # Compile
            optimizer = tf.keras.optimizers.Adam(
                learning_rate=config['learning_rate']
            )

            model.compile(
                optimizer=optimizer,
                loss='binary_crossentropy',
                metrics=[
                    'accuracy',
                    tf.keras.metrics.Precision(name='precision'),
                    tf.keras.metrics.Recall(name='recall')
                ]
            )

            param_count = model.count_params()
            print(f"Parameters:      {param_count:,}")

            # Callbacks - reduced patience for faster training
            callback_list = [
                tf.keras.callbacks.EarlyStopping(
                    monitor='val_loss',
                    patience=12,  # Reduced from 20 for faster stopping
                    restore_best_weights=True,
                    verbose=0
                )
            ]

            if config.get('use_lr_schedule'):
                callback_list.append(
                    tf.keras.callbacks.ReduceLROnPlateau(
                        monitor='val_loss',
                        factor=0.5,
                        patience=8,
                        min_lr=1e-7,
                        verbose=1
                    )
                )

            # Train
            train_start = datetime.now()
            print(f"\n  [START] Training at {train_start.strftime('%H:%M:%S')}")

            history = model.fit(
                self.X_train, self.y_train,
                validation_data=(self.X_val, self.y_val),
                epochs=config.get('epochs', 150),
                batch_size=config['batch_size'],
                callbacks=callback_list,
                verbose=0
            )

            train_end = datetime.now()
            train_time = (train_end - train_start).total_seconds()
            epochs_run = len(history.history['loss'])
            print(f"  [STOP]  Training completed at {train_end.strftime('%H:%M:%S')} ({train_time:.1f}s, {epochs_run} epochs)")

            # Evaluate
            train_metrics = model.evaluate(self.X_train, self.y_train, verbose=0)
            val_metrics = model.evaluate(self.X_val, self.y_val, verbose=0)

            train_loss, train_acc, train_prec, train_rec = train_metrics
            val_loss, val_acc, val_prec, val_rec = val_metrics

            # Calculate F1 scores
            train_f1 = 2 * (train_prec * train_rec) / (train_prec + train_rec + 1e-10)
            val_f1 = 2 * (val_prec * val_rec) / (val_prec + val_rec + 1e-10)

            # Inference speed
            inference_times = []
            sample_input = self.X_val[:1]

            # Warmup
            for _ in range(5):
                _ = model.predict(sample_input, verbose=0)

            # Measure
            for _ in range(50):
                start = time.time()
                _ = model.predict(sample_input, verbose=0)
                inference_times.append((time.time() - start) * 1000)

            avg_inference = float(np.mean(inference_times))

            # Calculate overfitting gap
            overfitting_gap = float(train_acc - val_acc)

            # Print results
            print(f"\n{'--- Results ---'}")
            print(f"Training Time:   {train_time:.1f}s ({len(history.history['loss'])} epochs)")
            print(f"\nTraining Set:")
            print(f"  Accuracy:  {train_acc:.4f} ({train_acc*100:.2f}%)")
            print(f"  Precision: {train_prec:.4f}")
            print(f"  Recall:    {train_rec:.4f}")
            print(f"  F1 Score:  {train_f1:.4f}")
            print(f"\nValidation Set:")
            print(f"  Accuracy:  {val_acc:.4f} ({val_acc*100:.2f}%)")
            print(f"  Precision: {val_prec:.4f}")
            print(f"  Recall:    {val_rec:.4f}")
            print(f"  F1 Score:  {val_f1:.4f}")
            print(f"\nPerformance:")
            print(f"  Inference:     {avg_inference:.2f}ms")
            print(f"  Overfitting:   {overfitting_gap*100:.2f}% gap")

            # Check requirements (90% accuracy, <6% overfit)
            meets_acc = val_acc >= 0.90
            meets_inference = avg_inference < 200
            meets_gap = overfitting_gap < 0.06

            print(f"\n{'='*60}")
            print(f"Accuracy >=90%:        {'PASS' if meets_acc else 'FAIL'}")
            print(f"Inference <200ms:      {'PASS' if meets_inference else 'FAIL'}")
            print(f"Gap <6%:               {'PASS' if meets_gap else 'FAIL'}")

            # Check for test mode
            test_mode = os.environ.get('CLASSIFIER_TEST_MODE', '0') == '1'

            all_pass = meets_acc and meets_inference and meets_gap
            if all_pass or test_mode:
                if all_pass:
                    print(f"\n*** ALL REQUIREMENTS MET! ***")

                # Save model (always save in test mode for validation)
                model_path = f"excellent_{name}.keras"
                model.save(model_path)
                if test_mode and not all_pass:
                    print(f"[SAVED] Model saved (test mode): {model_path}")
                else:
                    print(f"[SAVED] Model saved: {model_path}")
            else:
                # Save as candidate - don't leave user with nothing
                model_path = f"excellent_{name}_CANDIDATE.keras"
                model.save(model_path)
                print(f"[WARNING] Model did not meet criteria (acc={val_acc:.4f}, gap={overfitting_gap:.4f})")
                print(f"[SAVED] Saving as candidate: {model_path}")

            print(f"{'='*60}")

            # Store results (convert all to native Python types)
            result = {
                'name': str(name),
                'architecture': str(config['architecture']),
                'learning_rate': float(config['learning_rate']),
                'batch_size': int(config['batch_size']),
                'l2_reg': float(config.get('l2_reg', 0.0)),
                'dropout_rates': [float(x) for x in config.get('dropout_rates', (0.3, 0.4, 0.5))],
                'use_lr_schedule': bool(config.get('use_lr_schedule', False)),
                'params': int(param_count),
                'epochs_run': int(len(history.history['loss'])),
                'train_time': float(train_time),
                'train_acc': float(train_acc),
                'train_prec': float(train_prec),
                'train_rec': float(train_rec),
                'train_f1': float(train_f1),
                'val_acc': float(val_acc),
                'val_prec': float(val_prec),
                'val_rec': float(val_rec),
                'val_f1': float(val_f1),
                'inference_ms': float(avg_inference),
                'overfitting_gap': float(overfitting_gap),
                'meets_requirements': bool(all_pass)
            }

            self.results.append(result)
            return result

        except Exception as e:
            print(f"\n[ERROR] Training {name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run_search(self, configs):
        """Run hyperparameter search on all configurations with robustness scoring"""
        print(f"\n{'='*80}")
        print(f"CNN HYPERPARAMETER SEARCH - {len(configs)} CONFIGURATIONS")
        print(f"{'='*80}")
        print(f"Selection criteria: Robustness Score (accuracy × overfit penalty)")
        print(f"Target: >=90% val accuracy, <200ms inference, <6% gap")
        print(f"{'='*80}")

        best_score = -1
        best_config_name = None

        for i, config in enumerate(configs, 1):
            print(f"\n\n>>> Configuration {i}/{len(configs)}: {config.get('name', 'unnamed')}")
            result = self.train_single_config(config)

            if result:
                # Check for suspicious results
                is_suspicious, suspicious_reason = is_suspicious_result(result['val_acc'], result['overfitting_gap'])

                # Calculate robustness score
                rob_score = calculate_robustness_score(result['val_acc'], result['overfitting_gap'])
                result['robustness_score'] = rob_score
                result['rejected'] = is_suspicious
                result['rejection_reason'] = suspicious_reason if is_suspicious else None

                if is_suspicious:
                    print(f"\n  [X] REJECTED: {suspicious_reason}")
                    print(f"  >> Robustness Score: REJECTED (memorization suspected)")
                else:
                    print(f"\n  >> Robustness Score: {rob_score:.4f}")

                    if rob_score > best_score:
                        best_score = rob_score
                        best_config_name = result['name']
                        print(f"  >> NEW BEST!")

        self.best_config_name = best_config_name
        self.best_score = best_score

        return self.results

    def save_results(self, filename='results_round2.json'):
        """Save results to JSON with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"{Path(filename).stem}_{timestamp}.json"

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n[OK] Results saved: {filepath}")
        return filepath

    def print_summary(self):
        """Print comprehensive summary sorted by robustness score"""
        if not self.results:
            print("No results to summarize")
            return

        print(f"\n\n{'='*100}")
        print(f"SUMMARY - RANKED BY ROBUSTNESS SCORE")
        print(f"{'='*100}")

        # Separate rejected and valid results
        valid_results = [r for r in self.results if not r.get('rejected', False)]
        rejected_results = [r for r in self.results if r.get('rejected', False)]

        print(f"\nTotal configs: {len(self.results)}")
        print(f"Valid: {len(valid_results)}, Rejected (memorization): {len(rejected_results)}")

        # Sort valid results by robustness score
        sorted_results = sorted(
            valid_results,
            key=lambda x: x.get('robustness_score', x['val_acc']),
            reverse=True
        )

        if sorted_results:
            # Table header
            print(f"\n{'Rank':<6}{'Name':<25}{'Rob.Score':<12}{'Val Acc':<12}{'Gap':<10}{'Status'}")
            print(f"{'-'*100}")

            for i, r in enumerate(sorted_results, 1):
                status = '[PASS]' if r['meets_requirements'] else '[FAIL]'
                rob_score = r.get('robustness_score', 0)
                marker = " <-- BEST" if hasattr(self, 'best_config_name') and r['name'] == self.best_config_name else ""
                print(
                    f"{i:<6}"
                    f"{r['name']:<25}"
                    f"{rob_score:>8.4f}   "
                    f"{r['val_acc']*100:>6.2f}%     "
                    f"{r['overfitting_gap']*100:>5.1f}%    "
                    f"{status}{marker}"
                )

            # Best model details
            best = sorted_results[0]
            print(f"\n{'='*100}")
            print(f"[BEST] MODEL: {best['name']}")
            print(f"{'='*100}")
            print(f"  Architecture:         {best['architecture']}")
            print(f"  Validation Accuracy:  {best['val_acc']:.4f} ({best['val_acc']*100:.2f}%)")
            print(f"  Validation F1:        {best['val_f1']:.4f}")
            print(f"  Overfitting Gap:      {best['overfitting_gap']*100:.2f}%")
            print(f"  Inference Time:       {best['inference_ms']:.2f}ms")
            print(f"  Parameters:           {best['params']:,}")
            print(f"  Training Time:        {best['train_time']:.1f}s")
            print(f"  Batch Size:           {best['batch_size']}")
            print(f"  Learning Rate:        {best['learning_rate']}")
        else:
            print(f"\n[!] WARNING: No valid models found! All configs showed signs of memorization.")

        # Passing models
        passing = [r for r in valid_results if r['meets_requirements']]
        print(f"\n{'='*100}")
        print(f"Models meeting ALL requirements: {len(passing)}/{len(valid_results)} (excluding rejected)")
        if passing:
            print(f"\nPassing models:")
            for r in passing:
                print(f"  - {r['name']:<30} {r['val_acc']*100:.2f}% acc, {r['overfitting_gap']*100:.1f}% gap")

        # Show rejected models
        if rejected_results:
            print(f"\nRejected configs (memorization suspected):")
            for r in rejected_results:
                print(f"  - {r['name']}: val={r['val_acc']*100:.1f}%, gap={r['overfitting_gap']*100:.2f}% - {r.get('rejection_reason', 'suspicious')}")

        print(f"{'='*100}\n")


def is_suspicious_result(val_acc, overfit_gap):
    """
    Check if results are suspiciously perfect (likely memorization).

    Reject models with:
    - 98%+ accuracy (suspiciously high, likely memorized)
    - <0.3% overfitting gap (suspiciously low, suggests data leakage or memorization)

    These metrics look "too good" but indicate the model memorized training data
    rather than learning generalizable patterns.
    """
    if val_acc >= 0.98:
        return True, f"Val accuracy {val_acc*100:.1f}% >= 98% (likely memorization)"

    gap = abs(overfit_gap) if overfit_gap is not None else 0.0
    if gap < 0.003:
        return True, f"Overfitting gap {gap*100:.2f}% < 0.3% (suspiciously low)"

    return False, ""


def calculate_robustness_score(val_acc, overfit_gap):
    """
    Calculate robustness-aware score that penalizes overfitting.

    A model with 90% accuracy and 2% gap is BETTER than
    a model with 94% accuracy and 10% gap.

    ALSO: Reject models that are "too perfect" (memorization indicators)
    - 98%+ accuracy → returns -1 (rejected)
    - <0.3% gap → returns -1 (rejected)
    """
    # Check for suspicious results first
    is_suspicious, reason = is_suspicious_result(val_acc, overfit_gap)
    if is_suspicious:
        return -1.0  # Rejected

    gap = abs(overfit_gap)

    if gap < 0.03:
        penalty = 1.0  # Excellent generalization
    elif gap < 0.06:
        penalty = 0.97  # Acceptable
    elif gap < 0.10:
        penalty = 0.90  # Concerning
    elif gap < 0.15:
        penalty = 0.80  # Overfitting
    else:
        penalty = 0.65  # Severe overfitting

    return val_acc * penalty


def get_round2_configs():
    """
    Generate up to 7 configurations exploring regularization and learning rate.

    Strategy: All configs use the proven architecture (config_4) but vary:
    - Dropout rates (primary regularization)
    - L2 regularization strength
    - Learning rate
    - Batch size

    Robustness is prioritized over raw accuracy.
    """
    configs = [
        # Config 1: Baseline with slightly more epochs
        {
            'name': 'baseline',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4),
            'l2_reg': 0.0001,
            'epochs': 30
        },
        # Config 2: Higher dropout (more regularization)
        {
            'name': 'high_dropout',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.4, 0.5),
            'l2_reg': 0.0002,
            'epochs': 35
        },
        # Config 3: Lower learning rate
        {
            'name': 'slow_learner',
            'architecture': 'config_4',
            'learning_rate': 0.0005,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4),
            'l2_reg': 0.0001,
            'epochs': 40
        },
        # Config 4: Stronger L2 regularization
        {
            'name': 'strong_l2',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4),
            'l2_reg': 0.0005,
            'epochs': 35
        },
        # Config 5: Conservative (very high regularization)
        {
            'name': 'conservative',
            'architecture': 'config_4',
            'learning_rate': 0.0008,
            'batch_size': 24,
            'dropout_rates': (0.4, 0.5),
            'l2_reg': 0.0003,
            'epochs': 40
        },
        # Config 6: Larger batch, higher LR
        {
            'name': 'larger_batch',
            'architecture': 'config_4',
            'learning_rate': 0.0015,
            'batch_size': 32,
            'dropout_rates': (0.3, 0.4),
            'l2_reg': 0.0002,
            'epochs': 30
        },
        # Config 7: Very conservative
        {
            'name': 'very_conservative',
            'architecture': 'config_4',
            'learning_rate': 0.0006,
            'batch_size': 20,
            'dropout_rates': (0.45, 0.55),
            'l2_reg': 0.0004,
            'epochs': 45
        },
    ]

    return configs


def main():
    """Main execution"""
    import os

    # Check for test mode from environment variable
    test_mode = os.environ.get('CLASSIFIER_TEST_MODE', '0') == '1'

    print("="*80)
    print("Recipe Validator CNN - Round 2 Hyperparameter Search")
    if test_mode:
        print("*** TEST MODE: 1 config, 1 epoch ***")
    print("="*80)

    try:
        # Load data
        X_train, y_train, X_val, y_val = load_recipe_data('recipe_dataset_v2.npz')

        # Initialize search
        search = HyperparameterSearch(X_train, y_train, X_val, y_val)

        # Get configurations
        configs = get_round2_configs()

        # In test mode, use only 1 config with 1 epoch
        if test_mode:
            print("\n[TEST MODE] Using 1 config with 1 epoch")
            test_config = configs[0].copy()
            test_config['epochs'] = 1
            configs = [test_config]

        # Run search
        results = search.run_search(configs)

        # Save and summarize
        search.save_results()
        search.print_summary()

        print("\n[OK] Round 2 search complete!")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\nPlease ensure 'recipe_dataset_v2.npz' exists in the current directory.")
        print("The file should contain: X_train, y_train, X_val, y_val")

    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()