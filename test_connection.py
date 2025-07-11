#!/usr/bin/env python3
"""
Test de conexión a IBKR
Verifica conectividad y datos de mercado antes del trading
"""

import asyncio
import logging
from ib_insync import IB, Stock
from src.core.orb_config import ORBConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)

async def test_ibkr_connection():
    """Test de conexión completo a IBKR"""
    
    # Cargar configuración
    config = ORBConfig.load_from_file()
    
    print("🔌 TESTING IBKR CONNECTION")
    print("="*50)
    print(f"Host: {config.ibkr_host}")
    print(f"Port: {config.ibkr_port}")
    print(f"Client ID: {config.ibkr_client_id}")
    print(f"Symbol: {config.symbol}")
    print(f"Max Position: ${config.max_position_size}")
    print("-"*50)
    
    ib = IB()
    
    try:
        # Step 1: Conectar
        print("🔄 Connecting to TWS...")
        await ib.connectAsync(config.ibkr_host, config.ibkr_port, clientId=config.ibkr_client_id)
        
        if ib.isConnected():
            print("✅ Successfully connected to IBKR!")
            
            # Step 2: Verificar cuenta
            account_summary = ib.accountSummary()
            if account_summary:
                for item in account_summary:
                    if item.tag == 'TotalCashValue':
                        print(f"💰 Account Balance: {item.value} {item.currency}")
                    elif item.tag == 'BuyingPower':
                        print(f"📈 Buying Power: {item.value} {item.currency}")
            
            # Step 3: Test NVDA contract
            print(f"\n📊 Testing {config.symbol} contract...")
            nvda_contract = Stock(config.symbol, 'SMART', 'USD')
            
            # Obtener detalles del contrato
            contract_details = ib.reqContractDetails(nvda_contract)
            if contract_details:
                print(f"✅ {config.symbol} contract found:")
                detail = contract_details[0]
                print(f"   Exchange: {detail.contract.primaryExchange}")
                print(f"   Currency: {detail.contract.currency}")
                print(f"   Market Name: {detail.marketName}")
            
            # Step 4: Test market data
            print(f"\n📈 Requesting market data for {config.symbol}...")
            ib.reqMktData(nvda_contract, '', False, False)
            
            # Esperar un poco para recibir datos
            await asyncio.sleep(3)
            
            # Obtener ticker
            ticker = ib.ticker(nvda_contract)
            if ticker:
                print(f"✅ Market data received:")
                print(f"   Last Price: ${ticker.last:.2f}")
                print(f"   Bid: ${ticker.bid:.2f}")
                print(f"   Ask: ${ticker.ask:.2f}")
                print(f"   Volume: {ticker.volume:,}")
                
                # Calcular posición con precio actual
                if ticker.last > 0:
                    shares = int(config.max_position_size / ticker.last)
                    position_value = shares * ticker.last
                    risk_amount = position_value * abs(config.stop_loss_pct)
                    reward_amount = position_value * config.take_profit_pct
                    
                    print(f"\n💰 POSITION CALCULATION:")
                    print(f"   Current Price: ${ticker.last:.2f}")
                    print(f"   Shares (${config.max_position_size} max): {shares}")
                    print(f"   Position Value: ${position_value:.2f}")
                    print(f"   Stop Loss: ${ticker.last * (1 + config.stop_loss_pct):.2f} (Risk: ${risk_amount:.2f})")
                    print(f"   Take Profit: ${ticker.last * (1 + config.take_profit_pct):.2f} (Reward: ${reward_amount:.2f})")
                    
                    if risk_amount > 0:
                        print(f"   Risk/Reward: 1:{reward_amount/risk_amount:.1f}")
            else:
                print("⚠️ No market data received - may be outside market hours")
            
            # Step 5: Test real-time bars
            print(f"\n📊 Testing real-time bars...")
            try:
                ib.reqRealTimeBars(nvda_contract, 5, 'TRADES', False)
                print("✅ Real-time bars subscription successful")
                
                # Esperar algunas barras
                await asyncio.sleep(10)
                
                # Cancelar suscripción
                ib.cancelRealTimeBars(nvda_contract)
                print("✅ Real-time bars cancelled")
                
            except Exception as e:
                print(f"⚠️ Real-time bars test failed: {e}")
            
            # Step 6: Limpiar
            ib.cancelMktData(nvda_contract)
            
        else:
            print("❌ Failed to connect to IBKR")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Make sure TWS/IB Gateway is running")
        print("2. Check that API connections are enabled in TWS")
        print("3. Verify the port number (7496 for live, 7497 for paper)")
        print("4. Try a different client ID if connection is refused")
        return False
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("\n👋 Disconnected from IBKR")
    
    print("\n✅ CONNECTION TEST COMPLETED SUCCESSFULLY!")
    print("\n🚀 READY FOR LIVE TRADING!")
    print("   Use: python3 orb_trader.py --max-position 500")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_ibkr_connection())