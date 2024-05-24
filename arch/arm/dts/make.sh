#!/bin/bash

# Run the clean target
make -f device_tree_compiler.mk clean

# Run the default build target
make -f device_tree_compiler.mk
