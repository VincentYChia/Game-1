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
            "epochs": 100,
            "early_stopping_patience": 16
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

        # Save if good
        if val_f1 >= 0.90:
            model_path = self.model_save_dir / f"{model_name}_f1{val_f1:.4f}_model.keras"
            self.model.save(model_path)
            print(f"✓ Model saved: {model_path.name}")

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
        """Generate variations around best config"""

        import copy

        variations = []

        # 1. Original best config
        variations.append(('best_original', copy.deepcopy(self.best_config)))

        # 2. Vary filters (±4 per layer)
        for filters in [[20, 40], [24, 48], [28, 56]]:
            config = copy.deepcopy(self.best_config)
            config['filters'] = filters
            variations.append((f'filters_{filters[0]}_{filters[1]}', config))

        # 3. Vary kernel sizes
        for kernels in [[3, 3], [5, 5], [3, 5], [5, 3]]:
            config = copy.deepcopy(self.best_config)
            config['kernel_sizes'] = kernels
            variations.append((f'kernels_{kernels[0]}_{kernels[1]}', config))

        # 4. Vary dropout_conv (±0.05)
        for dropout in [0.15, 0.21, 0.25, 0.3]:
            config = copy.deepcopy(self.best_config)
            config['dropout_conv'] = dropout
            variations.append((f'dropout_conv_{dropout:.2f}', config))

        # 5. Vary dropout_dense (±0.05)
        for dropout in [0.6, 0.67, 0.7, 0.75]:
            config = copy.deepcopy(self.best_config)
            config['dropout_dense'] = dropout
            variations.append((f'dropout_dense_{dropout:.2f}', config))

        # 6. Vary L2 regularization (±0.003)
        for l2 in [0.007, 0.01, 0.012, 0.015]:
            config = copy.deepcopy(self.best_config)
            config['l2_regularization'] = l2
            variations.append((f'l2_{l2:.3f}', config))

        # 7. Vary learning rate
        for lr in [0.003, 0.005, 0.007]:
            config = copy.deepcopy(self.best_config)
            config['learning_rate'] = lr
            variations.append((f'lr_{lr:.3f}', config))

        # 8. Vary batch size
        for bs in [16, 24, 32]:
            config = copy.deepcopy(self.best_config)
            config['batch_size'] = bs
            variations.append((f'batch_{bs}', config))

        # 9. Try optimizer variations
        for opt in ['adam', 'adamw', 'rmsprop']:
            config = copy.deepcopy(self.best_config)
            config['optimizer'] = opt
            variations.append((f'optimizer_{opt}', config))

        # 10. Combinations of best tweaks
        # Slightly higher dropout + slightly higher L2
        config = copy.deepcopy(self.best_config)
        config['dropout_dense'] = 0.7
        config['l2_regularization'] = 0.012
        variations.append(('combo_higher_reg', config))

        # Slightly lower dropout + lower L2
        config = copy.deepcopy(self.best_config)
        config['dropout_dense'] = 0.6
        config['l2_regularization'] = 0.007
        variations.append(('combo_lower_reg', config))

        # Larger model
        config = copy.deepcopy(self.best_config)
        config['filters'] = [28, 56]
        config['dense_units'] = [128]
        config['dropout_dense'] = 0.7
        variations.append(('combo_larger', config))

        # Remove duplicates
        unique_variations = []
        seen = set()
        for name, config in variations:
            config_str = json.dumps(config, sort_keys=True)
            if config_str not in seen:
                seen.add(config_str)
                unique_variations.append((name, config))

        return unique_variations

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
        print(f"✓ Summary saved to: {summary_path}")


# Example usage
if __name__ == "__main__":
    import random

    random.seed(42)
    np.random.seed(42)
    tf.random.set_seed(42)

    trainer = BestModelVariationTrainer("adornment_dataset.npz")

    results = trainer.train_all_variations()

    print(f"\n✓ Trained {len(results)} variations!")
    print("Run comprehensive_model_evaluator.py to compare all models.")


    def build_model(self, config):
        """Build CNN with aggressive regularization"""

        input_shape = self.X_train.shape[1:]

        # Extract config
        filters = config['filters']
        kernel_size = config.get('kernel_size', 3)
        dropout_conv = config['dropout_conv']
        dropout_dense = config['dropout_dense']
        l2_reg = config['l2_regularization']
        use_batchnorm = config.get('batch_normalization', True)
        use_spatial_dropout = config.get('spatial_dropout', True)

        model = models.Sequential()
        model.add(layers.Input(shape=input_shape))

        # Add Gaussian noise to inputs (data augmentation)
        if config.get('input_noise', 0) > 0:
            model.add(layers.GaussianNoise(config['input_noise']))

        # Convolutional blocks
        for i, num_filters in enumerate(filters):
            # First conv
            model.add(layers.Conv2D(
                num_filters, (kernel_size, kernel_size),
                activation='relu',
                padding='same',
                kernel_regularizer=regularizers.l2(l2_reg),
                kernel_initializer='he_normal'  # Better initialization
            ))
            if use_batchnorm:
                model.add(layers.BatchNormalization())

            # Second conv
            model.add(layers.Conv2D(
                num_filters, (kernel_size, kernel_size),
                activation='relu',
                padding='same',
                kernel_regularizer=regularizers.l2(l2_reg),
                kernel_initializer='he_normal'
            ))
            if use_batchnorm:
                model.add(layers.BatchNormalization())

            model.add(layers.MaxPooling2D((2, 2)))

            # Spatial dropout better for conv layers
            if use_spatial_dropout:
                model.add(layers.SpatialDropout2D(dropout_conv))
            else:
                model.add(layers.Dropout(dropout_conv))

        # Dense layers
        model.add(layers.Flatten())

        for units in config['dense_units']:
            model.add(layers.Dense(
                units,
                activation='relu',
                kernel_regularizer=regularizers.l2(l2_reg),
                kernel_initializer='he_normal'
            ))
            if use_batchnorm:
                model.add(layers.BatchNormalization())
            model.add(layers.Dropout(dropout_dense))

        # Output with optional label smoothing
        model.add(layers.Dense(1, activation='sigmoid'))

        return model


    def get_anti_overfit_config(self, architecture='simple'):
        """Get pre-configured anti-overfitting setup"""

        configs = {
            'simple': {
                'filters': [24, 48],
                'dense_units': [64],
                'kernel_size': 3,
                'dropout_conv': 0.3,
                'dropout_dense': 0.7,  # High dense dropout
                'l2_regularization': 0.015,  # Strong L2
                'batch_normalization': True,
                'spatial_dropout': True,
                'input_noise': 0.05,  # Add input noise
                'learning_rate': 0.003,
                'batch_size': 32,
                'label_smoothing': 0.1,  # Prevent overconfidence
                'epochs': 150,
                'early_stopping_patience': 20
            },
            'medium': {
                'filters': [32, 64, 128],
                'dense_units': [128, 64],
                'kernel_size': 3,
                'dropout_conv': 0.35,
                'dropout_dense': 0.65,
                'l2_regularization': 0.012,
                'batch_normalization': True,
                'spatial_dropout': True,
                'input_noise': 0.05,
                'learning_rate': 0.002,
                'batch_size': 32,
                'label_smoothing': 0.1,
                'epochs': 150,
                'early_stopping_patience': 20
            },
            'robust': {
                'filters': [20, 40, 80],
                'dense_units': [64],
                'kernel_size': 3,
                'dropout_conv': 0.4,
                'dropout_dense': 0.75,  # Very high dropout
                'l2_regularization': 0.02,  # Very strong L2
                'batch_normalization': True,
                'spatial_dropout': True,
                'input_noise': 0.08,  # More noise
                'learning_rate': 0.002,
                'batch_size': 48,  # Larger batches
                'label_smoothing': 0.15,  # More smoothing
                'epochs': 150,
                'early_stopping_patience': 25
            }
        }

        return configs.get(architecture, configs['simple'])


    def create_data_generator(self, X, y, batch_size, augment=True):
        """Create data generator with on-the-fly augmentation"""

        def generator():
            indices = np.arange(len(X))

            while True:
                np.random.shuffle(indices)

                for start_idx in range(0, len(X), batch_size):
                    batch_indices = indices[start_idx:start_idx + batch_size]
                    batch_X = X[batch_indices].copy()
                    batch_y = y[batch_indices].copy()

                    if augment:
                        # Random horizontal flip
                        flip_mask = np.random.rand(len(batch_X)) > 0.5
                        batch_X[flip_mask] = batch_X[flip_mask, :, ::-1, :]

                        # Random vertical flip
                        flip_mask = np.random.rand(len(batch_X)) > 0.5
                        batch_X[flip_mask] = batch_X[flip_mask, ::-1, :, :]

                        # Random brightness adjustment
                        brightness = np.random.uniform(0.9, 1.1, (len(batch_X), 1, 1, 1))
                        batch_X = np.clip(batch_X * brightness, 0, 1)

                        # Random noise
                        noise = np.random.normal(0, 0.02, batch_X.shape)
                        batch_X = np.clip(batch_X + noise, 0, 1)

                    yield batch_X, batch_y

        steps_per_epoch = int(np.ceil(len(X) / batch_size))
        return generator(), steps_per_epoch


    def train(self, config=None, architecture='simple'):
        """Train model with anti-overfitting strategies"""

        if config is None:
            config = self.get_anti_overfit_config(architecture)

        print(f"\n{'=' * 80}")
        print(f"ANTI-OVERFITTING TRAINING - {architecture.upper()}")
        print(f"{'=' * 80}")
        print(f"Architecture: {config['filters']}")
        print(f"Dense: {config['dense_units']}")
        print(f"Dropout: conv={config['dropout_conv']}, dense={config['dropout_dense']}")
        print(f"L2 Regularization: {config['l2_regularization']}")
        print(f"Label Smoothing: {config.get('label_smoothing', 0)}")
        print(f"Input Noise: {config.get('input_noise', 0)}")
        print(f"Spatial Dropout: {config.get('spatial_dropout', False)}")
        print(f"Learning Rate: {config['learning_rate']}")
        print(f"Batch Size: {config['batch_size']}")
        print(f"{'=' * 80}\n")

        # Build model
        self.model = self.build_model(config)

        # Compile with label smoothing
        label_smoothing = config.get('label_smoothing', 0)
        loss = keras.losses.BinaryCrossentropy(label_smoothing=label_smoothing)

        optimizer = keras.optimizers.Adam(learning_rate=config['learning_rate'])

        self.model.compile(
            optimizer=optimizer,
            loss=loss,
            metrics=['accuracy',
                     keras.metrics.Precision(name='precision'),
                     keras.metrics.Recall(name='recall')]
        )

        print(self.model.summary())

        # Create data generators with augmentation
        train_gen, train_steps = self.create_data_generator(
            self.X_train, self.y_train,
            config['batch_size'],
            augment=True
        )

        # Callbacks
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_name = f"anti_overfit_{architecture}_{timestamp}"

        callback_list = [
            # Early stopping - monitor validation loss with patience
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=config.get('early_stopping_patience', 20),
                restore_best_weights=True,
                verbose=1,
                min_delta=0.0001  # Only stop if no improvement
            ),

            # Reduce learning rate more aggressively
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=7,  # Reduce patience
                min_lr=1e-7,
                verbose=1
            ),

            # Save best model
            callbacks.ModelCheckpoint(
                filepath=str(self.model_save_dir / f"{model_name}_best.keras"),
                monitor='val_loss',
                save_best_only=True,
                verbose=1
            ),

            # Stop if overfitting detected
            callbacks.EarlyStopping(
                monitor='accuracy',  # Monitor train accuracy
                patience=10,
                baseline=0.999,  # Stop if train acc > 99.9%
                verbose=1,
                mode='max'
            )
        ]

        # Train with data augmentation
        start_time = datetime.now()

        self.history = self.model.fit(
            train_gen,
            steps_per_epoch=train_steps,
            epochs=config.get('epochs', 150),
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

        # Calculate overfitting
        acc_gap = train_acc - val_acc
        f1_gap = train_f1 - val_f1

        print(f"\n{'=' * 80}")
        print("FINAL RESULTS")
        print(f"{'=' * 80}")
        print(f"Training:")
        print(f"  Accuracy: {train_acc:.4f}")
        print(f"  F1 Score: {train_f1:.4f}")
        print(f"Validation:")
        print(f"  Accuracy: {val_acc:.4f}")
        print(f"  F1 Score: {val_f1:.4f}")
        print(f"Overfitting:")
        print(f"  Accuracy Gap: {acc_gap:.4f}")
        print(f"  F1 Gap: {f1_gap:.4f}")

        if acc_gap < 0.05:
            print(f"  Level: ✓ LOW (Excellent!)")
        elif acc_gap < 0.10:
            print(f"  Level: ⚠ MEDIUM")
        else:
            print(f"  Level: ✗ HIGH")

        print(f"{'=' * 80}\n")

        # Save config and results
        results = {
            'model_name': model_name,
            'architecture': architecture,
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

        print(f"✓ Model saved to: {self.model_save_dir / f'{model_name}_best.keras'}")
        print(f"✓ Results saved to: {results_path}")

        return results


    def train_multiple_configs(self):
        """Train multiple anti-overfitting configurations"""

        architectures = ['simple', 'medium', 'robust']
        all_results = []

        for arch in architectures:
            print(f"\n{'#' * 80}")
            print(f"TRAINING: {arch.upper()}")
            print(f"{'#' * 80}")

            try:
                result = self.train(architecture=arch)
                all_results.append(result)
            except Exception as e:
                print(f"ERROR training {arch}: {e}")
                continue

        # Print comparison
        print(f"\n{'=' * 80}")
        print("COMPARISON OF ALL CONFIGS")
        print(f"{'=' * 80}")
        print(f"{'Architecture':<15} {'Val Acc':>10} {'Val F1':>10} {'Acc Gap':>10} {'Level':>10}")
        print(f"{'-' * 80}")

        for result in sorted(all_results, key=lambda x: x['overfitting']['accuracy_gap']):
            arch = result['architecture']
            val_acc = result['val_metrics']['accuracy']
            val_f1 = result['val_metrics']['f1']
            gap = result['overfitting']['accuracy_gap']

            if gap < 0.05:
                level = "LOW ✓"
            elif gap < 0.10:
                level = "MEDIUM ⚠"
            else:
                level = "HIGH ✗"

            print(f"{arch:<15} {val_acc:>10.4f} {val_f1:>10.4f} {gap:>10.4f} {level:>10}")

        print(f"{'=' * 80}\n")

        return all_results

# Example usage
if __name__ == "__main__":
    import random

    random.seed(42)
    np.random.seed(42)
    tf.random.set_seed(42)

    trainer = AntiOverfitCNNTrainer("adornment_dataset.npz")

    # Option 1: Train single config
    # result = trainer.train(architecture='simple')

    # Option 2: Train all configs and compare
    results = trainer.train_multiple_configs()

    print("\n✓ Anti-overfitting training complete!")
    print("Run comprehensive_model_evaluator.py to compare with previous models.")