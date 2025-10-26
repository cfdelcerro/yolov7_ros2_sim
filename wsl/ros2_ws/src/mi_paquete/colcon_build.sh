#!/bin/bash
# Este script se ejecuta después del build

echo "🔧 Post-build: Corrigiendo shebangs..."

INSTALL_DIR="$COLCON_PREFIX_PATH/lib/mi_paquete"

if [ -d "$INSTALL_DIR" ]; then
    for script in "$INSTALL_DIR"/*; do
        if [ -f "$script" ] && [ -x "$script" ]; then
            if head -n 1 "$script" | grep -q "python"; then
                sed -i "1s|^#!.*python.*|#!/home/usuario/yolo_ws/bin/python3|" "$script"
                echo "  ✓ $(basename $script)"
            fi
        fi
    done
fi
