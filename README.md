# What is this?

These are a set of tools I wrote while hacking the Orange Pi 2G-IOT to run a custom linux distribution. There is a detailed guide/tutorial at https://www.aib42.net/article/hacking-orangepi-2g. (Backup at https://www.aib.link/article/hacking-orangepi-2g)

# How do I use...

## opi2g_bin_read.py

#### Run `opi2g_bin_read.py` for help

This script analyzes an Android image used by the NAND update tool. If you supply a second argument, it extracts the file segments there.

#### Example Usage:

`opi2g_bin_read.py ~/Downloads/OrangePi_2G-IOT_Nand_Startup_V1.3.bin /tmp/extracted`

## opi2g_nand_write.py

#### Run `opi2g_nand_write.py --help` for help

This is a NAND flasher. It loads two extra bootloader stages (PDL1 and PDL2) and then tries to flash the given partitions using the given files. The partition table needs to be baked into PDL2. The partition loading code in PDL2 needs to be patched as well (see issue #1); if it is not patched you need to either format the flash using `--format-flash` or reboot the device once after loading PDL2.

I have [a fork](https://github.com/aib/u-boot-RDA8810) of U-Boot-RDA8810 suitable for creating a PDL2 as well as a NAND bootloader.

#### Example Usage:

`opi2g_nand_write.py -p /dev/ttyACM0 --format-flash --pdl1 pdl1.bin --pdl2 pdl2.bin bootloader:u-boot.rda nandroot:ubi.img`
