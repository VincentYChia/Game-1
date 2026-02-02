"""
Recipe Validator CNN - Round 2 Hyperparameter Search
Clean implementation with proper data handling and architectures
"""

import numpy as np
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

    print(f"✓ Dataset loaded successfully")
    print(f"  Train samples: {len(X_train)}")
    print(f"  Val samples:   {len(X_val)}")
    print(f"  Input shape:   {X_train.shape[1:]}")
    print(f"  Data type:     {X_train.dtype}")

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
            start_time = time.time()
            history = model.fit(
                self.X_train, self.y_train,
                validation_data=(self.X_val, self.y_val),
                epochs=config.get('epochs', 150),
                batch_size=config['batch_size'],
                callbacks=callback_list,
                verbose=0
            )
            train_time = time.time() - start_time

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

            # Check requirements
            meets_acc = val_acc >= 0.70
            meets_inference = avg_inference < 200
            meets_gap = overfitting_gap < 0.15

            print(f"\n{'='*60}")
            print(f"✓ Accuracy ≥70%:       {'PASS ✓' if meets_acc else 'FAIL ✗'}")
            print(f"✓ Inference <200ms:    {'PASS ✓' if meets_inference else 'FAIL ✗'}")
            print(f"✓ Gap <15%:            {'PASS ✓' if meets_gap else 'FAIL ✗'}")

            all_pass = meets_acc and meets_inference and meets_gap
            if all_pass:
                print(f"\n🎉 ALL REQUIREMENTS MET! 🎉")

                # Save excellent model
                model_path = f"excellent_{name}.keras"
                model.save(model_path)
                print(f"🎯 Model saved: {model_path}")

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
            print(f"\n❌ ERROR training {name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run_search(self, configs):
        """Run hyperparameter search on all configurations"""
        print(f"\n{'='*80}")
        print(f"HYPERPARAMETER SEARCH - ROUND 2")
        print(f"{'='*80}")
        print(f"Testing {len(configs)} configurations")
        print(f"Target: ≥70% val accuracy, <200ms inference, <15% gap")
        print(f"{'='*80}")

        for i, config in enumerate(configs, 1):
            print(f"\n\n>>> Configuration {i}/{len(configs)}")
            self.train_single_config(config)

        return self.results

    def save_results(self, filename='results_round2.json'):
        """Save results to JSON with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"{Path(filename).stem}_{timestamp}.json"

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n✓ Results saved: {filepath}")
        return filepath

    def print_summary(self):
        """Print comprehensive summary"""
        if not self.results:
            print("No results to summarize")
            return

        print(f"\n\n{'='*100}")
        print(f"SUMMARY - All Configurations")
        print(f"{'='*100}")

        # Sort by validation accuracy
        sorted_results = sorted(
            self.results,
            key=lambda x: x['val_acc'],
            reverse=True
        )

        # Table header
        print(f"\n{'Rank':<6}{'Name':<28}{'Val Acc':<12}{'Gap':<10}{'Infer':<12}{'Status'}")
        print(f"{'-'*100}")

        for i, r in enumerate(sorted_results, 1):
            status = '🎉 PASS' if r['meets_requirements'] else '   FAIL'
            print(
                f"{i:<6}"
                f"{r['name']:<28}"
                f"{r['val_acc']*100:>6.2f}%     "
                f"{r['overfitting_gap']*100:>5.1f}%    "
                f"{r['inference_ms']:>6.1f}ms    "
                f"{status}"
            )

        # Best model details
        best = sorted_results[0]
        print(f"\n{'='*100}")
        print(f"🏆 BEST MODEL: {best['name']}")
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

        # Passing models
        passing = [r for r in self.results if r['meets_requirements']]
        print(f"\n{'='*100}")
        print(f"✓ Models meeting ALL requirements: {len(passing)}/{len(self.results)}")
        if passing:
            print(f"\nPassing models:")
            for r in passing:
                print(f"  • {r['name']:<30} {r['val_acc']*100:.2f}% acc, {r['overfitting_gap']*100:.1f}% gap")
        print(f"{'='*100}\n")


def get_round2_configs():
    """
    Define streamlined configurations - MAX 6 MODELS to avoid excessive training time.

    We prioritize:
    1. Low overfitting (most important concern)
    2. Reasonable validation accuracy
    3. Fast training

    Reduced epochs from 150 to 60 to prevent overfitting.
    Early stopping will handle convergence.
    """

    configs = [
        # Config 1: Best architecture (minimal) with standard settings
        {
            'name': 'minimal_batch_16',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 16,
            'dropout_rates': (0.3, 0.4),
            'epochs': 60  # Reduced from 150
        },

        # Config 2: Minimal with batch 20 (sweet spot)
        {
            'name': 'minimal_batch_20',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4),
            'epochs': 60
        },

        # Config 3: Minimal with L2 regularization (anti-overfit)
        {
            'name': 'minimal_l2_reg',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4),
            'l2_reg': 0.0001,
            'epochs': 60
        },

        # Config 4: Medium architecture (slightly more capacity)
        {
            'name': 'medium_width',
            'architecture': 'config_5',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4, 0.4),
            'epochs': 60
        },

        # Config 5: Higher dropout for anti-overfit
        {
            'name': 'minimal_high_dropout',
            'architecture': 'config_4',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.4, 0.5),
            'epochs': 60
        },

        # Config 6: Wider architecture (more capacity)
        {
            'name': 'wider_batch_20',
            'architecture': 'config_3',
            'learning_rate': 0.001,
            'batch_size': 20,
            'dropout_rates': (0.3, 0.4, 0.5),
            'epochs': 60
        },
    ]

    return configs


def main():
    """Main execution"""
    print("="*80)
    print("Recipe Validator CNN - Round 2 Hyperparameter Search")
    print("="*80)

    try:
        # Load data
        X_train, y_train, X_val, y_val = load_recipe_data('recipe_dataset.npz')

        # Initialize search
        search = HyperparameterSearch(X_train, y_train, X_val, y_val)

        # Get configurations
        configs = get_round2_configs()

        # Run search
        results = search.run_search(configs)

        # Save and summarize
        search.save_results()
        search.print_summary()

        print("\n✓ Round 2 search complete!")

    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print("\nPlease ensure 'recipe_dataset.npz' exists in the current directory.")
        print("The file should contain: X_train, y_train, X_val, y_val")

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()