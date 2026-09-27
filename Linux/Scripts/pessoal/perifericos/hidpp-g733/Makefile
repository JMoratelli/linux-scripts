KVER ?= $(shell uname -r)
KDIR := /usr/lib/modules/$(KVER)/build
# o kernel do CachyOS e compilado com clang/LTO; o modulo precisa do mesmo
LLVMFLAG := $(if $(shell grep -s '^CONFIG_CC_IS_CLANG=y' $(KDIR)/.config),LLVM=1)
all:
	$(MAKE) -j2 -C $(KDIR) M=$(CURDIR) $(LLVMFLAG) modules
clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) $(LLVMFLAG) clean
