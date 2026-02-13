#!/usr/bin/env python3
"""
ONNX Model Conversion Script — Phase 5 ML Classifier Migration
================================================================

Converts all 5 classifier models from native formats to ONNX for Unity Sentis.

CNN models (Keras .keras): Uses tf2onnx
LightGBM models (.txt):   Uses onnxmltools

Prerequisites:
    pip install tensorflow tf2onnx onnx onnxruntime lightgbm onnxmltools

Usage:
    cd Game-1
    python Unity/Assets/Scripts/Game1.Systems/Classifiers/Scripts/convert_models_to_onnx.py

Output:
    Unity/Assets/Resources/Models/*.onnx (5 files)
"""

import os
import sys
import numpy as np
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[6]  # Game-1/
MODELS_DIR = PROJECT_ROOT / "Scaled JSON Development" / "models"
OUTPUT_DIR = PROJECT_ROOT / "Unity" / "Assets" / "Resources" / "Models"

CNN_MODELS = {
    "smithing": {
        "input_path": MODELS_DIR / "smithing" / "smithing_best.keras",
        "output_path": OUTPUT_DIR / "smithing.onnx",
        "input_shape": [1, 36, 36, 3],
    },
    "adornments": {
        "input_path": MODELS_DIR / "adornment" / "adornment_best.keras",
        "output_path": OUTPUT_DIR / "adornments.onnx",
        "input_shape": [1, 56, 56, 3],
    },
}

LGBM_MODELS = {
    "alchemy": {
        "input_path": MODELS_DIR / "alchemy" / "alchemy_model.txt",
        "output_path": OUTPUT_DIR / "alchemy.onnx",
        "num_features": 34,
    },
    "refining": {
        "input_path": MODELS_DIR / "refining" / "refining_model.txt",
        "output_path": OUTPUT_DIR / "refining.onnx",
        "num_features": 19,
    },
    "engineering": {
        "input_path": MODELS_DIR / "engineering" / "engineering_model.txt",
        "output_path": OUTPUT_DIR / "engineering.onnx",
        "num_features": 28,
    },
}

OPSET_VERSION = 15

# ============================================================================
# CNN Conversion (Keras -> ONNX via tf2onnx)
# ============================================================================

def convert_cnn_model(name, config):
    """Convert a Keras CNN model to ONNX."""
    print(f"\n{'='*60}")
    print(f"Converting CNN model: {name}")
    print(f"  Input:  {config['input_path']}")
    print(f"  Output: {config['output_path']}")
    print(f"{'='*60}")

    if not config["input_path"].exists():
        print(f"  ERROR: Model file not found: {config['input_path']}")
        return False

    try:
        import tensorflow as tf
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

        # Load Keras model
        print(f"  Loading Keras model...")
        model = tf.keras.models.load_model(str(config["input_path"]))
        print(f"  Model loaded: input={model.input_shape}, output={model.output_shape}")

        # Convert via tf2onnx
        import tf2onnx
        print(f"  Converting to ONNX (opset {OPSET_VERSION})...")

        input_shape = config["input_shape"]
        spec = (tf.TensorSpec(input_shape, tf.float32, name="input"),)
        onnx_model, _ = tf2onnx.convert.from_keras(
            model, input_signature=spec, opset=OPSET_VERSION
        )

        # Save
        config["output_path"].parent.mkdir(parents=True, exist_ok=True)
        import onnx
        onnx.save(onnx_model, str(config["output_path"]))
        size_mb = config["output_path"].stat().st_size / (1024 * 1024)
        print(f"  Saved: {config['output_path']} ({size_mb:.2f} MB)")

        # Validate
        print(f"  Validating ONNX model...")
        validate_cnn_onnx(name, config)
        return True

    except Exception as e:
        print(f"  ERROR: Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_cnn_onnx(name, config):
    """Validate ONNX CNN model output matches Keras."""
    import tensorflow as tf
    import onnxruntime as ort

    keras_model = tf.keras.models.load_model(str(config["input_path"]))
    ort_session = ort.InferenceSession(str(config["output_path"]))

    input_name = ort_session.get_inputs()[0].name
    shape = config["input_shape"]
    num_tests = 100
    max_diff = 0

    for i in range(num_tests):
        test_input = np.random.rand(*shape).astype(np.float32)

        keras_pred = float(keras_model.predict(test_input, verbose=0)[0][0])
        ort_pred = float(ort_session.run(None, {input_name: test_input})[0][0][0])

        diff = abs(keras_pred - ort_pred)
        max_diff = max(max_diff, diff)

        if diff >= 0.001:
            print(f"    WARNING: Test {i}: Keras={keras_pred:.6f}, "
                  f"ONNX={ort_pred:.6f}, diff={diff:.6f}")

    print(f"  Validation: {num_tests} tests, max diff={max_diff:.8f} "
          f"({'PASS' if max_diff < 0.001 else 'FAIL'})")


# ============================================================================
# LightGBM Conversion (Booster .txt -> ONNX via onnxmltools)
# ============================================================================

def convert_lgbm_model(name, config):
    """Convert a LightGBM model to ONNX."""
    print(f"\n{'='*60}")
    print(f"Converting LightGBM model: {name}")
    print(f"  Input:  {config['input_path']}")
    print(f"  Output: {config['output_path']}")
    print(f"  Features: {config['num_features']}")
    print(f"{'='*60}")

    if not config["input_path"].exists():
        print(f"  ERROR: Model file not found: {config['input_path']}")
        return False

    try:
        import lightgbm as lgb
        import onnxmltools
        from onnxmltools.convert import convert_lightgbm
        from onnxmltools.convert.common.data_types import FloatTensorType

        # Load LightGBM model
        print(f"  Loading LightGBM Booster...")
        booster = lgb.Booster(model_file=str(config["input_path"]))
        print(f"  Model loaded: {booster.num_feature()} features, "
              f"best_iteration={booster.best_iteration}")

        assert booster.num_feature() == config["num_features"], (
            f"Feature count mismatch: model has {booster.num_feature()}, "
            f"expected {config['num_features']}"
        )

        # Convert
        print(f"  Converting to ONNX (opset {OPSET_VERSION})...")
        initial_type = [("input", FloatTensorType([None, config["num_features"]]))]
        onnx_model = convert_lightgbm(
            booster, initial_types=initial_type, target_opset=OPSET_VERSION
        )

        # Save
        config["output_path"].parent.mkdir(parents=True, exist_ok=True)
        onnxmltools.utils.save_model(onnx_model, str(config["output_path"]))
        size_kb = config["output_path"].stat().st_size / 1024
        print(f"  Saved: {config['output_path']} ({size_kb:.1f} KB)")

        # Validate
        print(f"  Validating ONNX model...")
        validate_lgbm_onnx(name, config)
        return True

    except Exception as e:
        print(f"  ERROR: Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_lgbm_onnx(name, config):
    """Validate ONNX LightGBM model output matches native."""
    import lightgbm as lgb
    import onnxruntime as ort

    booster = lgb.Booster(model_file=str(config["input_path"]))
    ort_session = ort.InferenceSession(str(config["output_path"]))

    input_name = ort_session.get_inputs()[0].name
    num_features = config["num_features"]
    num_tests = 100
    max_diff = 0

    for i in range(num_tests):
        test_input = np.random.rand(1, num_features).astype(np.float32)

        lgbm_pred = float(booster.predict(
            test_input, num_iteration=booster.best_iteration)[0])

        ort_output = ort_session.run(None, {input_name: test_input})
        # LightGBM ONNX output format may vary — handle both cases
        if len(ort_output) > 1:
            # Probability output (second output for classifiers)
            ort_pred = float(ort_output[1][0][1])  # class 1 probability
        else:
            ort_pred = float(ort_output[0][0])

        diff = abs(lgbm_pred - ort_pred)
        max_diff = max(max_diff, diff)

        if diff >= 0.001:
            print(f"    WARNING: Test {i}: LightGBM={lgbm_pred:.6f}, "
                  f"ONNX={ort_pred:.6f}, diff={diff:.6f}")

    print(f"  Validation: {num_tests} tests, max diff={max_diff:.8f} "
          f"({'PASS' if max_diff < 0.001 else 'FAIL'})")


# ============================================================================
# Main
# ============================================================================

def main():
    print(f"ONNX Model Conversion — Phase 5 ML Classifiers")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Models dir:   {MODELS_DIR}")
    print(f"Output dir:   {OUTPUT_DIR}")
    print(f"ONNX opset:   {OPSET_VERSION}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # Convert CNN models
    for name, config in CNN_MODELS.items():
        results[name] = convert_cnn_model(name, config)

    # Convert LightGBM models
    for name, config in LGBM_MODELS.items():
        results[name] = convert_lgbm_model(name, config)

    # Summary
    print(f"\n{'='*60}")
    print(f"CONVERSION SUMMARY")
    print(f"{'='*60}")
    for name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  {name:15s} [{status}]")

    all_pass = all(results.values())
    print(f"\nOverall: {'ALL PASSED' if all_pass else 'SOME FAILED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
