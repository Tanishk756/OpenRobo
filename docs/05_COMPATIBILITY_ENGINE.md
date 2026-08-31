# Compatibility Engine

The engine determines compatibility among resources and explains the result.

States:
- compatible
- conditional
- incompatible
- unknown

Inputs can include:
OS, architecture, ROS/middleware version, language/runtime, compiler, CUDA/GPU, firmware, protocol, driver, hardware interfaces, simulator, dependencies, and license constraints.

The engine must distinguish:
1. Declared compatibility
2. Automatically inferred compatibility
3. Empirically tested compatibility
4. Community-reported compatibility

It must never present an unverified inference as a tested fact.
