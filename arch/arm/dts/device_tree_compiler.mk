# Makefile to preprocess and compile Device Tree Source

# Variables
DTC = dtc
CPP = cpp
SRC_DIR = .
BUILD_DIR = $(SRC_DIR)/build

# Default target device tree, but can be overridden
TARGET ?= zynq-zed

# Default all target
all: $(BUILD_DIR)/$(TARGET).dtb

# Create build directory if it doesn't exist
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Preprocess the Device Tree Source files
$(BUILD_DIR)/$(TARGET).dts.tmp: $(SRC_DIR)/$(TARGET).dts $(SRC_DIR)/zynq-7000.dtsi | $(BUILD_DIR)
	$(CPP) -nostdinc -I$(SRC_DIR) -undef -D__DTS__ -x assembler-with-cpp $< -o $@

# Compile the preprocessed Device Tree Source into a Device Tree Blob
$(BUILD_DIR)/$(TARGET).dtb: $(BUILD_DIR)/$(TARGET).dts.tmp
	$(DTC) -O dtb -o $@ -b 0 -i $(SRC_DIR) -W no-unit_address_vs_reg $<

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)

# Phony targets for make commands
.PHONY: all clean
