SOURCE_IMAGES=$(wildcard *.png)
IMAGES=$(SOURCE_IMAGES:%.png=%.bin) face.bin

%.bin: %.png
	./makebin --dither none "$<" > "$@"

all: main.py vcard.py $(IMAGES)
	mpremote cp $^ :
