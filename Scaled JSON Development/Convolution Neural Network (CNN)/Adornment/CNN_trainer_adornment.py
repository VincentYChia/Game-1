import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, callbacks, regularizers
import json
from pathlib import Path
from datetime import datetime
import itertools


class TargetedConfigurationSearch:
    """Targeted search based on successful configuration patterns"""

    def __init__(self, dataset_path, results_dir="targeted_results"):
        self.dataset_path = dataset_path
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)

        # Load dataset
        print("Loading dataset...")
        data = np.load(dataset_path)
        self.X_train = data['X_train']
        self.y_train = data['y_train']
        self.X_val = data['X_val']
        self.y_val = data['y_val']

        print(f"Training: {self.X_train.shape[0]} samples")
        print(f"Validation: {self.X_val.shape[0]} samples\n")

        self.all_results = []

    def build_model(self, config):
        """Build model with configuration"""

        input_shape = self.X_train.shape[1:]
        model = models.Sequential()
        model.add(layers.Input(shape=input_shape))

        # Get config params
        filters = config['filters']
        kernel_size = config.get('kernel_size', 3)
        dropout_conv = config['dropout_conv']
        dropout_dense = config['dropout_dense']
        l2_reg = config['l2_regularization']
        batch_norm = config.get('batch_normalization', True)
        activation = config.get('activation', 'relu')

        # Convolutional blocks
        for num_filters in filters:
            # First conv in block
            model.add(layers.Conv2D(
                num_filters, (kernel_size, kernel_size),
                activation=activation,
                padding='same',
                kernel_regularizer=regularizers.l2(l2_reg) if l2_reg > 0 else None
            ))
            if batch_norm:
                model.add(layers.BatchNormalization())

            # Second conv in block
            model.add(layers.Conv2D(
                num_filters, (kernel_size, kernel_size),
                activation=activation,
                padding='same',
                kernel_regularizer=regularizers.l2(l2_reg) if l2_reg > 0 else None
            ))
            if batch_norm:
                model.add(layers.BatchNormalization())

            model.add(layers.MaxPooling2D((2, 2)))
            model.add(layers.Dropout(dropout_conv))

        # Dense layers
        model.add(layers.Flatten())

        for units in config['dense_units']:
            model.add(layers.Dense(
                units,
                activation=activation,
                kernel_regularizer=regularizers.l2(l2_reg) if l2_reg > 0 else None
            ))
            if batch_norm:
                model.add(layers.BatchNormalization())
            model.add(layers.Dropout(dropout_dense))

        # Output
        model.add(layers.Dense(1, activation='sigmoid'))

        return model

    def train_configuration(self, config, experiment_name):
        """Train a configuration and return results"""

        print(f"\n{'=' * 80}")
        print(f"Experiment: {experiment_name}")
        print(f"Filters: {config['filters']}")
        print(f"Dense: {config['dense_units']}")
        print(f"Dropout: conv={config['dropout_conv']}, dense={config['dropout_dense']}")
        print(f"L2: {config['l2_regularization']}, LR: {config['learning_rate']}")
        print(f"Batch size: {config['batch_size']}")
        print(f"{'=' * 80}\n")

        # Build model
        model = self.build_model(config)

        # Compile
        optimizer = keras.optimizers.Adam(learning_rate=config['learning_rate'])

        model.compile(
            optimizer=optimizer,
            loss='binary_crossentropy',
            metrics=['accuracy',
                     keras.metrics.Precision(name='precision'),
                     keras.metrics.Recall(name='recall')]
        )

        # Callbacks
        callback_list = [
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=config.get('early_stopping_patience', 15),
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

        history = model.fit(
            self.X_train, self.y_train,
            batch_size=config['batch_size'],
            epochs=config.get('epochs', 100),
            validation_data=(self.X_val, self.y_val),
            callbacks=callback_list,
            verbose=1
        )

        train_time = (datetime.now() - start_time).total_seconds()

        # Evaluate
        val_results = model.evaluate(self.X_val, self.y_val, verbose=0)
        val_loss = val_results[0]
        val_accuracy = val_results[1]
        val_precision = val_results[2]
        val_recall = val_results[3]
        val_f1 = 2 * (val_precision * val_recall) / (val_precision + val_recall) if (
                                                                                                val_precision + val_recall) > 0 else 0

        best_epoch = np.argmin(history.history['val_loss'])

        # Compile results
        results = {
            'experiment_name': experiment_name,
            'timestamp': datetime.now().isoformat(),
            'config': config,
            'final_metrics': {
                'val_loss': float(val_loss),
                'val_accuracy': float(val_accuracy),
                'val_precision': float(val_precision),
                'val_recall': float(val_recall),
                'val_f1': float(val_f1)
            },
            'best_epoch': int(best_epoch),
            'total_epochs': len(history.history['loss']),
            'train_time_seconds': train_time,
            'model_params': model.count_params(),
            'history': {
                'val_accuracy': [float(x) for x in history.history['val_accuracy']],
                'val_loss': [float(x) for x in history.history['val_loss']]
            }
        }

        # Save if good (>80%)
        if val_accuracy >= 0.80:
            model_path = self.results_dir / f"{experiment_name}_acc{val_accuracy:.4f}_model.keras"
            model.save(model_path)
            results['model_path'] = str(model_path)

            print(f"\n{'=' * 80}")
            print(f"✓ GOOD CONFIG! Val Accuracy: {val_accuracy:.4f}, F1: {val_f1:.4f}")
            print(f"{'=' * 80}\n")
        else:
            print(f"\nVal Accuracy: {val_accuracy:.4f}, F1: {val_f1:.4f}")

        # Save results
        results_path = self.results_dir / f"{experiment_name}_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)

        # Cleanup
        del model
        tf.keras.backend.clear_session()

        return results

    def run_targeted_grid_search(self):
        """
        Grid search around successful patterns:
        - Simple architectures (2-3 blocks)
        - Small filters (16-64 range)
        - Small dense layers (32-128)
        - High dropout (0.5-0.7 for dense)
        - Strong L2 regularization (0.005-0.02)
        - Higher learning rates (0.003-0.01)
        """

        # Define targeted parameter grid
        param_grid = {
            'filters': [
                [16, 32],  # Very small
                [20, 40],  # Small
                [24, 48],  # Best so far (95%)
                [28, 56],  # Slightly larger
                [32, 64],  # Known good (82%)
                [40, 80],  # Medium
                [16, 32, 64],  # 3 blocks - small
                [20, 40, 80],  # 3 blocks - medium
                [24, 48, 96],  # 3 blocks - based on best
            ],
            'dense_units': [
                [32],
                [64],  # Known good
                [128],
                [64, 32],
            ],
            'dropout_conv': [0.15, 0.2, 0.25, 0.3, 0.35, 0.4],
            'dropout_dense': [0.5, 0.55, 0.6, 0.65, 0.7, 0.75],
            'l2_regularization': [0.005, 0.008, 0.01, 0.012, 0.015, 0.02],
            'learning_rate': [0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.01],
            'batch_size': [24, 32, 48],
        }

        # Generate all combinations
        keys = list(param_grid.keys())
        values = list(param_grid.values())

        # Calculate total combinations
        total_combos = 1
        for v in values:
            total_combos *= len(v)

        print(f"\n{'=' * 80}")
        print(f"TARGETED GRID SEARCH")
        print(f"{'=' * 80}")
        print(f"Total possible combinations: {total_combos:,}")
        print(f"This would take too long, so we'll use smart sampling...")
        print(f"{'=' * 80}\n")

        # Smart sampling: focus on promising regions
        configs_to_test = []

        # 1. Variations around best config (search_003: 95%)
        best_base = {
            'filters': [24, 48],
            'dense_units': [64],
            'dropout_conv': 0.21,
            'dropout_dense': 0.67,
            'l2_regularization': 0.01,
            'learning_rate': 0.005,
            'batch_size': 32,
            'epochs': 100,
            'early_stopping_patience': 15
        }

        # Vary filters around [24, 48]
        for f in [[20, 40], [24, 48], [28, 56], [32, 64]]:
            config = best_base.copy()
            config['filters'] = f
            configs_to_test.append(config)

        # Vary L2 around 0.01
        for l2 in [0.008, 0.01, 0.012, 0.015]:
            config = best_base.copy()
            config['l2_regularization'] = l2
            configs_to_test.append(config)

        # Vary dropout_dense around 0.67
        for dd in [0.6, 0.65, 0.67, 0.7, 0.75]:
            config = best_base.copy()
            config['dropout_dense'] = dd
            configs_to_test.append(config)

        # Vary learning rate around 0.005
        for lr in [0.003, 0.004, 0.005, 0.006, 0.008]:
            config = best_base.copy()
            config['learning_rate'] = lr
            configs_to_test.append(config)

        # 2. Variations around good config (search_001: 82%)
        good_base = {
            'filters': [32, 64],
            'dense_units': [64],
            'dropout_conv': 0.39,
            'dropout_dense': 0.57,
            'l2_regularization': 0.005,
            'learning_rate': 0.003,
            'batch_size': 32,
            'epochs': 100,
            'early_stopping_patience': 15
        }

        # Try with higher regularization
        for l2 in [0.008, 0.01, 0.012]:
            config = good_base.copy()
            config['l2_regularization'] = l2
            configs_to_test.append(config)

        # Try with higher dense dropout
        for dd in [0.6, 0.65, 0.7]:
            config = good_base.copy()
            config['dropout_dense'] = dd
            configs_to_test.append(config)

        # 3. Explore 3-block architectures
        for filters in [[16, 32, 64], [20, 40, 80], [24, 48, 96]]:
            config = best_base.copy()
            config['filters'] = filters
            configs_to_test.append(config)

        # 4. Try different dense configurations
        for dense in [[32], [128], [64, 32]]:
            config = best_base.copy()
            config['dense_units'] = dense
            configs_to_test.append(config)

        # Remove duplicates
        unique_configs = []
        seen = set()
        for config in configs_to_test:
            config_str = json.dumps(config, sort_keys=True)
            if config_str not in seen:
                seen.add(config_str)
                unique_configs.append(config)

        print(f"Testing {len(unique_configs)} unique configurations\n")

        # Train all configs
        for i, config in enumerate(unique_configs, 1):
            experiment_name = f"targeted_{i:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            try:
                results = self.train_configuration(config, experiment_name)
                self.all_results.append(results)
            except Exception as e:
                print(f"ERROR in {experiment_name}: {e}")
                continue

        # Save summary
        self._save_summary()

        return self.all_results

    def _save_summary(self):
        """Save summary of all experiments"""

        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_experiments': len(self.all_results),
            'experiments': []
        }

        for result in self.all_results:
            summary['experiments'].append({
                'name': result['experiment_name'],
                'config': result['config'],
                'metrics': result['final_metrics'],
                'model_params': result['model_params']
            })

        # Sort by validation accuracy
        summary['experiments'].sort(
            key=lambda x: x['metrics']['val_accuracy'],
            reverse=True
        )

        # Save summary
        summary_path = self.results_dir / f"targeted_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'=' * 80}")
        print("TARGETED SEARCH COMPLETE")
        print(f"{'=' * 80}")
        print(f"Total experiments: {len(self.all_results)}")

        # Show top 10
        print(f"\nTop 10 configurations by validation accuracy:")
        for i, exp in enumerate(summary['experiments'][:10], 1):
            metrics = exp['metrics']
            config = exp['config']
            print(f"\n{i}. {exp['name']}")
            print(f"   Val Accuracy: {metrics['val_accuracy']:.4f}")
            print(f"   Val F1:       {metrics['val_f1']:.4f}")
            print(f"   Filters:      {config['filters']}")
            print(f"   Dense:        {config['dense_units']}")
            print(f"   Dropout:      conv={config['dropout_conv']}, dense={config['dropout_dense']}")
            print(f"   L2:           {config['l2_regularization']}")
            print(f"   LR:           {config['learning_rate']}")

        print(f"\n✓ Summary saved to: {summary_path}")
        print(f"{'=' * 80}\n")


# Example usage
if __name__ == "__main__":
    import random

    random.seed(42)
    np.random.seed(42)
    tf.random.set_seed(42)

    searcher = TargetedConfigurationSearch("adornment_dataset.npz")

    results = searcher.run_targeted_grid_search()

    print(f"\nTested {len(results)} configurations!")

    # Count successful configs (>80%)
    successful = [r for r in results if r['final_metrics']['val_accuracy'] >= 0.80]
    excellent = [r for r in results if r['final_metrics']['val_accuracy'] >= 0.90]

    print(f"Successful (≥80%): {len(successful)}")
    print(f"Excellent (≥90%):  {len(excellen