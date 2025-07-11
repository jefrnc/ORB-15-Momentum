#!/usr/bin/env python3
"""
Test final para verificar que todo funciona correctamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, time
import pytz
from src.strategies.orb_strategy import ORBStrategy
from src.core.orb_config import ORBConfig

def test_strategy_methods():
    """Test que los métodos existen y funcionan"""
    print("🧪 Test 1: Verificando métodos de ORBStrategy...")
    
    config = ORBConfig()
    strategy = ORBStrategy(config)
    
    # Verificar que existe analyze_tick
    if hasattr(strategy, 'analyze_tick'):
        print("✅ Método analyze_tick existe")
    else:
        print("❌ ERROR: Método analyze_tick NO existe")
        return False
        
    # Verificar que NO existe analyze_candle
    if not hasattr(strategy, 'analyze_candle'):
        print("✅ Método analyze_candle correctamente removido")
    else:
        print("❌ ERROR: Método analyze_candle todavía existe")
        return False
    
    return True

def test_config_attributes():
    """Test que los atributos de config son correctos"""
    print("\n🧪 Test 2: Verificando atributos de ORBConfig...")
    
    config = ORBConfig()
    
    # Verificar que existe take_profit_ratio
    if hasattr(config, 'take_profit_ratio'):
        print(f"✅ Atributo take_profit_ratio existe: {config.take_profit_ratio}")
    else:
        print("❌ ERROR: Atributo take_profit_ratio NO existe")
        return False
        
    # Verificar que NO existe take_profit_pct
    if not hasattr(config, 'take_profit_pct'):
        print("✅ Atributo take_profit_pct correctamente removido")
    else:
        print("❌ ERROR: Atributo take_profit_pct todavía existe")
        return False
    
    return True

def test_strategy_simulation():
    """Test simulación básica de la estrategia"""
    print("\n🧪 Test 3: Simulando funcionamiento básico...")
    
    config = ORBConfig()
    strategy = ORBStrategy(config)
    
    # Simular un tick durante el ORB window
    ny_tz = pytz.timezone('America/New_York')
    orb_time = datetime.now(ny_tz).replace(hour=9, minute=35, second=0)
    
    tick = {
        'timestamp': orb_time,
        'price': 450.50,
        'volume': 100000,
        'last': 450.50
    }
    
    try:
        # Procesar tick para construcción del rango
        strategy.process_tick_for_range(tick)
        print("✅ process_tick_for_range funciona correctamente")
    except Exception as e:
        print(f"❌ ERROR en process_tick_for_range: {e}")
        return False
    
    # Simular análisis de tick fuera del ORB window
    entry_time = datetime.now(ny_tz).replace(hour=10, minute=30, second=0)
    tick['timestamp'] = entry_time
    tick['price'] = 452.00  # Por encima del rango
    
    try:
        signal = strategy.analyze_tick(tick)
        print("✅ analyze_tick funciona correctamente")
        if signal:
            print(f"   Señal generada: {signal}")
    except Exception as e:
        print(f"❌ ERROR en analyze_tick: {e}")
        return False
    
    return True

def test_imports():
    """Test que todos los imports funcionan"""
    print("\n🧪 Test 4: Verificando imports...")
    
    try:
        import orb_trader
        print("✅ orb_trader.py se puede importar")
    except Exception as e:
        print(f"❌ ERROR importando orb_trader: {e}")
        return False
        
    try:
        import orb_trader_simple
        print("✅ orb_trader_simple.py se puede importar")
    except Exception as e:
        print(f"❌ ERROR importando orb_trader_simple: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("VERIFICACIÓN FINAL - ORB Trading System")
    print("=" * 60)
    
    tests = [
        test_strategy_methods(),
        test_config_attributes(),
        test_strategy_simulation(),
        test_imports()
    ]
    
    print("\n" + "=" * 60)
    if all(tests):
        print("🎉 TODOS LOS TESTS PASARON - El sistema está listo!")
        print("\nPuedes ejecutar el bot con:")
        print("  python orb_trader_simple.py")
    else:
        print("⚠️  ALGUNOS TESTS FALLARON - Revisa los errores")
    print("=" * 60)