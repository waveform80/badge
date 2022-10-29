IMAGES=$(wildcard *.bin)

all: main.py vcard.py $(IMAGES)
	mpremote cp $^ :
