import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, callbacks, regularizers
import json
from pathlib import Path
from datetime import datetime


class BestModelVariationTrainer:
    """Create variations around the best performing model"""

    def __init__(self, dataset_path, model_save_dir="best_model_variations"):
        self.dataset_path = dataset_path
        self.model_save_dir = Path(model_save_dir)
        self.model_save_dir.mkdir(exist_ok=True)

        # Load dataset
        print("Loading dataset...")
        data = np.load(dataset_path)
        self.X_train = data['X_train']
        self.y_train = data['y_train']
        self.X_val = data['X_val']
        self.y_val = data['y_val']

        print(f"Training set: {self.X_train.shape[0]} examples")
        print(f"Validation set: {self.X_val.shape[0]} examples\n")

        # Best model config (search_003)
        # Epochs reduced from 100 to 50 to prevent overfitting
        self.best_config = {
            "architecture_type": "simple",
            "filters": [24, 48],
            "kernel_sizes": [5, 5],
            "dropout_conv": 0.21,
            "dropout_dense": 0.67,
            "dense_units": [64],
            "l2_regularization": 0.01,
            "batch_normalization": True,
            "learning_rate": 0.005,
            "optimizer": "adamw",
            "batch_size": 16,
            "activation": "relu",
            "pooling": "max",
            "use_global_pooling": False,
            "epochs": 50,  # Reduced from 100 to prevent overfitting
            "early_stopping_patience": 12  # Reduced from 16 for faster stopping
        }

        self.model = None
        self.history = None

    def build_model(self, config):
        """Build CNN with given config"""

        input_shape = self.X_train.shape[1:]

        filters = config['filters']
        kernel_sizes = config['kernel_sizes']
        dropout_conv = config['dropout_conv']
        dropout_dense = config['dropout_dense']
        l2_reg = config['l2_regularization']
        activation = config.get('activation', 'relu')
        use_batchnorm = config.get('batch_normalization', True)

        model = models.Sequential()
        model.add(layers.Input(shape=input_shape))

        # Convolutional blocks
        for i, (num_filters, kernel_size) in enumerate(zip(filters, kernel_sizes)):
            # First conv
            model.add(layers.Conv2D(
                num_filters, (kernel_size, kernel_size),
                activation=activation,
                padding='same',
                kernel_regularizer=regularizers.l2(l2_reg) if l2_reg > 0 else None
            ))
            if use_batchnorm:
                model.add(layers.BatchNormalization())

            # Second conv
            model.add(layers.Conv2D(
                num_filters, (kernel_size, kernel_size),
                activation=activation,
                padding='same',
                kernel_regularizer=regularizers.l2(l2_reg) if l2_reg > 0 else None
            ))
            if use_batchnorm:
                model.add(layers.BatchNormalization())

            # Pooling
            if config.get('pooling', 'max') == 'max':
                model.add(layers.MaxPooling2D((2, 2)))
            else:
                model.add(layers.AveragePooling2D((2, 2)))

            model.add(layers.Dropout(dropout_conv))

        # Dense layers
        if config.get('use_global_pooling', False):
            model.add(layers.GlobalAveragePooling2D())
        else:
            model.add(layers.Flatten())

        for units in config['dense_units']:
            model.add(layers.Dense(
                units,
                activation=activation,
                kernel_regularizer=regularizers.l2(l2_reg) if l2_reg > 0 else None
            ))
            if use_batchnorm:
                model.add(layers.BatchNormalization())
            model.add(layers.Dropout(dropout_dense))

        # Output
        model.add(layers.Dense(1, activation='sigmoid'))

        return model

    def train_config(self, config, variation_name):
        """Train a single configuration"""

        print(f"\n{'=' * 80}")
        print(f"Training: {variation_name}")
        print(f"{'=' * 80}")
        print(f"Filters: {config['filters']}")
        print(f"Kernel sizes: {config['kernel_sizes']}")
        print(f"Dense: {config['dense_units']}")
        print(f"Dropout: conv={config['dropout_conv']}, dense={config['dropout_dense']}")
        print(f"L2: {config['l2_regularization']}")
        print(f"LR: {config['learning_rate']}")
        print(f"Batch size: {config['batch_size']}")
        print(f"Optimizer: {config['optimizer']}")
        print(f"{'=' * 80}\n")

        # Build model
        self.model = self.build_model(config)

        # Compile
        lr = config['learning_rate']
        if config['optimizer'] == 'adam':
            optimizer = keras.optimizers.Adam(learning_rate=lr)
        elif config['optimizer'] == 'adamw':
            optimizer = keras.optimizers.AdamW(learning_rate=lr, weight_decay=0.0001)
        else:
            optimizer = keras.optimizers.RMSprop(learning_rate=lr)

        self.model.compile(
            optimizer=optimizer,
            loss='binary_crossentropy',
            metrics=['accuracy',
                     keras.metrics.Precision(name='precision'),
                     keras.metrics.Recall(name='recall')]
        )

        # Callbacks
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_name = f"{variation_name}_{timestamp}"

        callback_list = [
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=config.get('early_stopping_patience', 16),
                restore_best_weights=True,
                verbose=1
            ),
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-7,
                verbose=1
            )
        ]

        # Train
        start_time = datetime.now()

        self.history = self.model.fit(
            self.X_train, self.y_train,
            batch_size=config['batch_size'],
            epochs=config.get('epochs', 100),
            validation_data=(self.X_val, self.y_val),
            callbacks=callback_list,
            verbose=1
        )

        train_time = (datetime.now() - start_time).total_seconds()

        # Evaluate
        val_results = self.model.evaluate(self.X_val, self.y_val, verbose=0)
        train_results = self.model.evaluate(self.X_train, self.y_train, verbose=0)

        val_loss, val_acc, val_prec, val_rec = val_results
        train_loss, train_acc, train_prec, train_rec = train_results

        val_f1 = 2 * (val_prec * val_rec) / (val_prec + val_rec) if (val_prec + val_rec) > 0 else 0
        train_f1 = 2 * (train_prec * train_rec) / (train_prec + train_rec) if (train_prec + train_rec) > 0 else 0

        acc_gap = train_acc - val_acc
        f1_gap = train_f1 - val_f1

        print(f"\n{'=' * 80}")
        print("RESULTS")
        print(f"{'=' * 80}")
        print(f"Validation: Acc={val_acc:.4f}, F1={val_f1:.4f}")
        print(f"Training:   Acc={train_acc:.4f}, F1={train_f1:.4f}")
        print(f"Overfitting Gap: {acc_gap:.4f}")

        # Check requirements (90% accuracy, <6% overfit)
        meets_acc = val_acc >= 0.90
        meets_gap = acc_gap < 0.06
        print(f"Accuracy >=90%: {'PASS' if meets_acc else 'FAIL'}")
        print(f"Gap <6%:        {'PASS' if meets_gap else 'FAIL'}")

        # Check for test mode from environment
        import os
        test_mode = os.environ.get('CLASSIFIER_TEST_MODE', '0') == '1'

        # Save if meets criteria (90% acc, <6% gap) or always save in test mode
        all_pass = meets_acc and meets_gap
        if all_pass or test_mode:
            model_path = self.model_save_dir / f"{model_name}_acc{val_acc:.4f}_model.keras"
            self.model.save(model_path)
            if test_mode:
                print(f"[SAVED] Model saved (test mode): {model_path.name}")
            elif all_pass:
                print(f"[SAVED] Model saved (meets criteria): {model_path.name}")
            else:
                print(f"[SAVED] Model saved: {model_path.name}")

        # Save results
        results = {
            'variation_name': variation_name,
            'timestamp': datetime.now().isoformat(),
            'config': config,
            'train_metrics': {
                'accuracy': float(train_acc),
                'f1': float(train_f1),
                'precision': float(train_prec),
                'recall': float(train_rec)
            },
            'val_metrics': {
                'accuracy': float(val_acc),
                'f1': float(val_f1),
                'precision': float(val_prec),
                'recall': float(val_rec)
            },
            'overfitting': {
                'accuracy_gap': float(acc_gap),
                'f1_gap': float(f1_gap)
            },
            'train_time_seconds': train_time,
            'total_epochs': len(self.history.history['loss']),
            'model_params': self.model.count_params()
        }

        results_path = self.model_save_dir / f"{model_name}_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)

        # Cleanup
        del self.model
        tf.keras.backend.clear_session()

        return results

    def generate_variations(self):
        """
        Generate MAX 6 variations around best config.

        Streamlined to avoid excessive training time.
        Prioritizes:
        1. Low overfitting (most important)
        2. Reasonable validation accuracy
        3. Fast training

        Epochs reduced from 100 to 50.
        """

        import copy

        variations = []

        # Config 1: Original best config with reduced epochs
        config1 = copy.deepcopy(self.best_config)
        config1['epochs'] = 50  # Reduced from 100
        variations.append(('best_original', config1))

        # Config 2: Higher dropout for anti-overfit
        config2 = copy.deepcopy(self.best_config)
        config2['dropout_dense'] = 0.75
        config2['dropout_conv'] = 0.3
        config2['epochs'] = 50
        variations.append(('high_dropout', config2))

        # Config 3: Stronger L2 regularization
        config3 = copy.deepcopy(self.best_config)
        config3['l2_regularization'] = 0.015
        config3['epochs'] = 50
        variations.append(('strong_l2', config3))

        # Config 4: Smaller architecture (less overfitting risk)
        config4 = copy.deepcopy(self.best_config)
        config4['filters'] = [20, 40]
        config4['dense_units'] = [48]
        config4['epochs'] = 50
        variations.append(('smaller_arch', config4))

        # Config 5: Combined anti-overfit (higher dropout + higher L2)
        config5 = copy.deepcopy(self.best_config)
        config5['dropout_dense'] = 0.7
        config5['l2_regularization'] = 0.012
        config5['epochs'] = 50
        variations.append(('combo_antioverfit', config5))

        # Config 6: Larger batch size (more stable gradients)
        config6 = copy.deepcopy(self.best_config)
        config6['batch_size'] = 32
        config6['epochs'] = 50
        variations.append(('batch_32', config6))

        return variations

    def train_all_variations(self):
        """Train all variations"""

        variations = self.generate_variations()

        print(f"\n{'=' * 80}")
        print(f"TRAINING {len(variations)} VARIATIONS OF BEST MODEL")
        print(f"{'=' * 80}")
        print(f"Base model: search_003 (Val F1: 0.9481)")
        print(f"{'=' * 80}\n")

        all_results = []

        for i, (name, config) in enumerate(variations, 1):
            print(f"\n{'#' * 80}")
            print(f"VARIATION {i}/{len(variations)}: {name}")
            print(f"{'#' * 80}")

            try:
                result = self.train_config(config, name)
                all_results.append(result)
            except Exception as e:
                print(f"ERROR training {name}: {e}")
                continue

        # Save summary
        self._save_summary(all_results)

        return all_results

    def _save_summary(self, results):
        """Save summary of all variations"""

        summary = {
            'timestamp': datetime.now().isoformat(),
            'base_model': 'search_003',
            'total_variations': len(results),
            'variations': sorted(results, key=lambda x: x['val_metrics']['f1'], reverse=True)
        }

        summary_path = self.model_save_dir / f"variations_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'=' * 80}")
        print("SUMMARY - TOP 10 VARIATIONS")
        print(f"{'=' * 80}")
        print(f"{'Variation':<30} {'Val F1':>10} {'Val Acc':>10} {'Gap':>8}")
        print(f"{'-' * 80}")

        for result in summary['variations'][:10]:
            name = result['variation_name'][:29]
            val_f1 = result['val_metrics']['f1']
            val_acc = result['val_metrics']['accuracy']
            gap = result['overfitting']['accuracy_gap']

            print(f"{name:<30} {val_f1:>10.4f} {val_acc:>10.4f} {gap:>8.4f}")

        print(f"{'=' * 80}")
        print(f"[OK] Summary saved to: {summary_path}")


# Example usage
if __name__ == "__main__":
    import random
    import os

    random.seed(42)
    np.random.seed(42)
    tf.random.set_seed(42)

    # Check for test mode from environment variable
    test_mode = os.environ.get('CLASSIFIER_TEST_MODE', '0') == '1'

    if test_mode:
        print("="*80)
        print("*** TEST MODE: 1 config only ***")
        print("="*80)

    trainer = BestModelVariationTrainer("adornment_dataset_v2.npz")

    if test_mode:
        # Test mode: Run single variation only
        print("\n[TEST MODE] Running single variation only")
        import copy
        test_config = copy.deepcopy(trainer.best_config)
        test_config['epochs'] = 1
        result = trainer.train_config(test_config, "test_single")
        results = [result] if result else []
    else:
        results = trainer.train_all_variations()

    print(f"\n[OK] Trained {len(results)} variations!")
    print("Run comprehensive_model_evaluator.py to compare all models.")