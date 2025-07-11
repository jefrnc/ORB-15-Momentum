#!/usr/bin/env python3
"""
Timezone Helper - Obtener hora ET precisa desde fuentes externas
"""

import requests
import pytz
from datetime import datetime
import json

class TimezoneHelper:
    def __init__(self):
        self.et_tz = pytz.timezone('America/New_York')
        self.arg_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        
    def get_et_time_worldtime(self):
        """Obtener hora ET desde WorldTimeAPI"""
        try:
            response = requests.get(
                'http://worldtimeapi.org/api/timezone/America/New_York',
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                # Parsear datetime string
                dt_str = data['datetime']
                # Formato: 2025-07-02T09:50:30.123456-04:00
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                
                print(f"✅ WorldTimeAPI - ET: {dt.strftime('%H:%M:%S %Z')}")
                return dt
        except Exception as e:
            print(f"❌ Error WorldTimeAPI: {e}")
        return None
    
    def get_et_time_timeapi(self):
        """Obtener hora ET desde TimeAPI.io"""
        try:
            response = requests.get(
                'https://timeapi.io/api/Time/current/zone?timeZone=America/New_York',
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                # Construir datetime
                dt = datetime(
                    year=data['year'],
                    month=data['month'], 
                    day=data['day'],
                    hour=data['hour'],
                    minute=data['minute'],
                    second=data['seconds']
                )
                dt = self.et_tz.localize(dt)
                
                print(f"✅ TimeAPI.io - ET: {dt.strftime('%H:%M:%S %Z')}")
                return dt
        except Exception as e:
            print(f"❌ Error TimeAPI: {e}")
        return None
    
    def get_et_time_timezonedb(self):
        """Obtener hora ET desde TimezoneDB (requiere API key gratuita)"""
        try:
            # API key gratuita desde: https://timezonedb.com/register
            API_KEY = 'YOUR_API_KEY'  # Reemplazar con tu key
            
            response = requests.get(
                f'http://api.timezonedb.com/v2.1/get-time-zone',
                params={
                    'key': API_KEY,
                    'format': 'json',
                    'by': 'zone',
                    'zone': 'America/New_York'
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'OK':
                    dt = datetime.fromtimestamp(data['timestamp'])
                    dt = self.et_tz.localize(dt)
                    
                    print(f"✅ TimezoneDB - ET: {dt.strftime('%H:%M:%S %Z')}")
                    return dt
        except Exception as e:
            print(f"❌ Error TimezoneDB: {e}")
        return None
    
    def get_accurate_et_time(self):
        """
        Obtener hora ET precisa probando múltiples fuentes
        Retorna la primera que funcione
        """
        print("\n🌐 Obteniendo hora ET desde servicios externos...")
        
        # Intentar múltiples fuentes
        sources = [
            self.get_et_time_worldtime,
            self.get_et_time_timeapi,
            # self.get_et_time_timezonedb  # Descomentar si tienes API key
        ]
        
        for source in sources:
            et_time = source()
            if et_time:
                # Comparar con hora local
                local_et = datetime.now(self.et_tz)
                diff = abs((et_time - local_et).total_seconds())
                
                if diff > 60:  # Más de 1 minuto de diferencia
                    print(f"⚠️  Diferencia detectada: {diff:.0f} segundos")
                
                return et_time
        
        # Fallback a hora local
        print("⚠️  Usando hora local como fallback")
        return datetime.now(self.et_tz)
    
    def get_market_schedule(self, et_time=None):
        """Obtener horarios de mercado en ambas zonas"""
        if not et_time:
            et_time = self.get_accurate_et_time()
        
        arg_time = et_time.astimezone(self.arg_tz)
        
        # Calcular diferencia horaria actual
        hour_diff = arg_time.hour - et_time.hour
        if hour_diff < 0:
            hour_diff += 24
        
        schedule = {
            'current_et': et_time.strftime('%H:%M:%S %Z'),
            'current_arg': arg_time.strftime('%H:%M:%S %Z'),
            'hour_difference': hour_diff,
            'market_open_et': '09:30',
            'market_open_arg': f'{9+hour_diff:02d}:30',
            'orb_end_et': '09:45',
            'orb_end_arg': f'{9+hour_diff:02d}:45',
            'force_close_et': '15:00',
            'force_close_arg': f'{15+hour_diff:02d}:00',
            'market_close_et': '16:00',
            'market_close_arg': f'{16+hour_diff:02d}:00'
        }
        
        # Estado del mercado
        et_hour_min = et_time.hour + et_time.minute/60
        if et_time.weekday() >= 5:
            schedule['market_status'] = 'CERRADO (Fin de semana)'
        elif 9.5 <= et_hour_min < 16:
            schedule['market_status'] = 'ABIERTO'
        else:
            schedule['market_status'] = 'CERRADO'
        
        return schedule
    
    def print_market_info(self):
        """Imprimir información completa del mercado"""
        schedule = self.get_market_schedule()
        
        print("\n" + "="*60)
        print("📍 HORARIOS DE MERCADO NYSE - TIEMPO REAL")
        print("="*60)
        
        print(f"\n⏰ HORA ACTUAL:")
        print(f"   🇺🇸 ET (NYSE): {schedule['current_et']}")
        print(f"   🇦🇷 Argentina: {schedule['current_arg']}")
        print(f"   📊 Diferencia: {schedule['hour_difference']} hora(s)")
        
        print(f"\n📈 ESTADO: {schedule['market_status']}")
        
        print(f"\n🕐 HORARIOS DE HOY:")
        print(f"   Apertura:      {schedule['market_open_et']} ET → {schedule['market_open_arg']} ARG")
        print(f"   Fin ORB:       {schedule['orb_end_et']} ET → {schedule['orb_end_arg']} ARG")
        print(f"   Cierre Forzado: {schedule['force_close_et']} ET → {schedule['force_close_arg']} ARG")
        print(f"   Cierre Mercado: {schedule['market_close_et']} ET → {schedule['market_close_arg']} ARG")
        
        # Calcular próximo evento
        et_time = datetime.now(self.et_tz)
        current_minutes = et_time.hour * 60 + et_time.minute
        
        events = [
            (9*60+30, "Apertura"),
            (9*60+45, "Fin ORB"),
            (15*60, "Cierre Forzado"),
            (16*60, "Cierre Mercado")
        ]
        
        for event_minutes, event_name in events:
            if current_minutes < event_minutes:
                mins_until = event_minutes - current_minutes
                hours = mins_until // 60
                mins = mins_until % 60
                print(f"\n⏳ Próximo evento: {event_name} en {hours}h {mins}m")
                break
        
        print("="*60)

# Función helper para usar en otros scripts
def get_accurate_market_time():
    """Obtener hora ET precisa y estado del mercado"""
    helper = TimezoneHelper()
    return helper.get_market_schedule()

if __name__ == "__main__":
    # Test
    helper = TimezoneHelper()
    helper.print_market_info()