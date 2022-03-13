GITHUB=https://github.com
MP_PATH=../micropython
MP_REPO=$(GITHUB)/micropython/micropython
MP_VERSION=v1.18
PIMORONI_PICO_PATH=../pimoroni-pico
PIMORONI_PICO_REPO=$(GITHUB)/pimoroni/pimoroni-pico
PIMORONI_PICO_VERSION=main

all: firmware.uf2

clean:
	cd "$(MP_PATH)" && git clean -xfd
	cd "$(PIMORONI_PICO_PATH)" && git clean -xfd

$(MP_PATH):
	git clone "$(MP_REPO)" "$(MP_PATH)"
	cd "$(MP_PATH)" && git checkout "$(MP_VERSION)"
	cd "$(MP_PATH)" && git submodule update --init
	cd "$(MP_PATH)/lib/pico-sdk" && git submodule update --init

$(PIMORONI_PICO_PATH):
	git clone "$(PIMORONI_PICO_REPO)" "$(PIMORONI_PICO_PATH)"
	cd "$(PIMORONI_PICO_PATH)" && git checkout "$(PIMORONI_PICO_VERSION)"
	cd "$(PIMORONI_PICO_PATH)" && git submodule update --init

$(MP_PATH)/mpy-cross/mpy-cross: $(MP_PATH)
	cd "$(MP_PATH)"/mpy-cross && make

$(MP_PATH)/ports/rp2/boards/PICO/mpconfigboard.h: \
	$(PIMORONI_PICO_PATH)/micropython/badger2040-mpconfigboard.h \
	$(MP_PATH)/ports/rp2
	cp "$<" "$@"

$(MP_PATH)/ports/rp2: $(MP_PATH)

$(PIMORONI_PICO_PATH)/micropython/badger2040-mpconfigboard.h: $(PIMORONI_PICO_PATH)

$(PIMORONI_PICO_PATH)/micropython/modules/micropython.cmake: $(PIMORONI_PICO_PATH)

$(MP_PATH)/ports/rp2/build-PICO: \
	$(MP_PATH)/mpy-cross/mpy-cross \
	$(MP_PATH)/ports/rp2/boards/PICO/mpconfigboard.h \
	$(PIMORONI_PICO_PATH)/micropython/modules/micropython.cmake
	cd "$(abspath $(MP_PATH)/ports/rp2)" && cmake -S . -B "$(abspath $@)" \
		-DPICO_BUILD_DOCS=0 \
		-DUSER_C_MODULES="$(abspath $(PIMORONI_PICO_PATH)/micropython/modules/badger2040-micropython.cmake)" \
		-DMICROPY_BOARD=PICO

firmware.uf2: \
	main.py \
	$(MP_PATH)/mpy-cross/mpy-cross \
	$(MP_PATH)/ports/rp2/build-PICO
	cd "$(abspath $(MP_PATH)/ports/rp2)" && cmake --build build-PICO -j2
	cp "$(MP_PATH)"/ports/rp2/build-PICO/firmware.uf2 "$@"
