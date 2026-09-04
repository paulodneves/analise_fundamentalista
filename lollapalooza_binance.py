import math
import requests
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv

# Carrega chaves do .env
load_dotenv()

# --- CONFIGURAÇÕES ---
CONFIG = {
    "VOLUME_MINIMO_USDT": 5_000_000, 
    "CATEGORIAS_EXCLUIDAS": ['stablecoins', 'wrapped-tokens', 'meme-token'],
    "TOP_N_MARKETCAP": 250,
    "BINANCE_API_URL": "https://api.binance.com/api/v3"
}

print("🎸 INICIANDO ALGORITMO: CRYPTO LOLLAPALOOZA (Binance Real-Time Edition) 🚀")
print("==========================================================================")

def obter_limites_binance():
    """Busca o minNotional (mínimo em USDT) de todos os pares na Binance."""
    print("📡 Stage 0.1: Buscando limites operacionais da Binance...")
    try:
        response = requests.get(f"{CONFIG['BINANCE_API_URL']}/exchangeInfo")
        response.raise_for_status()
        info = response.json()
        
        limites = {}
        for s in info['symbols']:
            if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING':
                # O filtro NOTIONAL (ou MIN_NOTIONAL) define o valor mínimo da ordem em USDT
                for f in s['filters']:
                    if f['filterType'] in ['NOTIONAL', 'MIN_NOTIONAL']:
                        limites[s['baseAsset']] = float(f.get('minNotional') or f.get('notional') or 10.0)
                        break
        return limites
    except Exception as e:
        print(f"⚠️ Erro ao acessar Binance API: {e}. Usando fallback de 10 USDT.")
        return {}

def obter_dados_crypto():
    print("📥 Stage 0.2: Baixando dados fundamentais do CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": CONFIG["TOP_N_MARKETCAP"],
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h,7d,30d"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Erro ao baixar dados: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df[df['total_volume'] > CONFIG["VOLUME_MINIMO_USDT"]]
    
    stables = ['usdt', 'usdc', 'dai', 'busd', 'fdusd', 'pyusd', 'usde', 'tusd', 'usdp']
    df = df[~df['symbol'].str.lower().isin(stables)]
    df = df[df['ath_change_percentage'] > -98]
    
    return df

def stage_1_graham_crypto(df):
    print("🛡️ Stage 1: Filtro de Segurança (Graham Adaptado)...")
    df['supply_ratio'] = df['circulating_supply'] / df['total_supply']
    df['supply_ratio'] = df['supply_ratio'].fillna(1.0)
    
    candidatos = df[
        (df['supply_ratio'] >= 0.5) & 
        (df['ath_change_percentage'] <= -60)
    ].copy()
    
    return candidatos

def stage_2_quality_buffett(df):
    print("💎 Stage 2: Filtro de Qualidade (Buffett/Munger)...")
    df['turnover'] = df['total_volume'] / df['market_cap']
    
    candidatos = df[
        (df['market_cap_rank'] <= 150) &
        (df['turnover'] >= 0.01)
    ].copy()
    
    return candidatos

def stage_3_ranking_lollapalooza(df):
    print("⚖️ Stage 3: Calculando Score Lollapalooza...")
    resultados = []
    
    for _, row in df.iterrows():
        score = 0
        factors = []
        
        if row['market_cap_rank'] <= 20:
            score += 20
            factors.append("Blue Chip (Top 20)")
        elif row['market_cap_rank'] <= 50:
            score += 10
            factors.append("Tier 1 (Top 50)")
            
        if row['supply_ratio'] > 0.90:
            score += 15
            factors.append("Full Supply (Anti-Inflação)")
        elif row['supply_ratio'] > 0.75:
            score += 5
            factors.append("Good Tokenomics")
            
        desconto = abs(row['ath_change_percentage'])
        if desconto > 85:
            score += 25
            factors.append(f"Desconto Extremo ({desconto:.0f}%)")
        elif desconto > 70:
            score += 15
            factors.append("Desconto Graham (>70%)")
            
        if row['price_change_percentage_7d_in_currency'] > 10:
            score += 10
            factors.append("Força Relativa (7d+)")

        resultados.append({
            'Ativo': row['symbol'].upper(),
            'Nome': row['name'],
            'Preco': row['current_price'],
            'ATH': row['ath'],
            'Score': score,
            'Motivo': ", ".join(factors),
            'MarketCapRank': row['market_cap_rank']
        })

    return pd.DataFrame(resultados).sort_values(by=['Score', 'MarketCapRank'], ascending=[False, True])

def montar_carteira_binance(df_ranking, limites_binance):
    print("\n" + "="*80)
    print("💰 CALCULADORA DE ALOCAÇÃO CRYPTO (Mínimos Reais)")
    print("="*80)
    
    try:
        investimento = float(input(">>> Quanto deseja alocar na Binance (em USDT): "))
    except ValueError:
        print("Valor inválido.")
        return

    # Aprovados: Score >= 30
    top_picks = df_ranking[df_ranking['Score'] >= 30].copy()
    
    if top_picks.empty:
        print("⚠️ Nenhum ativo cripto atingiu os critérios de segurança/qualidade hoje.")
        return

    # Cruza com os limites da Binance
    top_picks['MinUSDT'] = top_picks['Ativo'].apply(lambda x: limites_binance.get(x, 10.0))
    
    # Remove ativos que não estão na Binance ou têm mínimo maior que o saldo total
    top_picks = top_picks[top_picks['Ativo'].isin(limites_binance)]
    if top_picks.empty:
        print("⚠️ Nenhum dos ativos selecionados está disponível para trading em USDT na Binance.")
        return

    # Lógica de Alocação respeitando mínimos individuais
    ativos_finais = []
    saldo_restante = investimento
    
    # Tenta alocar para os Top 10 respeitando os mínimos
    for _, row in top_picks.head(10).iterrows():
        min_necessario = row['MinUSDT']
        if saldo_restante >= min_necessario:
            alocacao_ideal = investimento / 10
            valor_alocado = max(min_necessario, min(alocacao_ideal, saldo_restante))
            
            # CÁLCULO DO PREÇO ALVO (Exit Strategy)
            # Lógica: Recuperar 50% da distância entre o preço atual e o topo histórico (ATH)
            distancia_ath = row['ATH'] - row['Preco']
            alvo_venda = row['Preco'] + (distancia_ath * 0.5)
            upside = (alvo_venda / row['Preco'] - 1) * 100

            ativos_finais.append({
                'Ativo': row['Ativo'],
                'Preco': row['Preco'],
                'Alvo_Venda': alvo_venda,
                'Upside_%': upside,
                'Valor_USDT': valor_alocado,
                'Min_Binance': min_necessario,
                'Motivo': row['Motivo']
            })
            saldo_restante -= valor_alocado

    if not ativos_finais:
        print(f"⚠️ Saldo insuficiente para atingir o mínimo de qualquer ativo selecionado.")
        return

    # Distribui o que sobrou proporcionalmente no primeiro
    if saldo_restante > 0:
        ativos_finais[0]['Valor_USDT'] += saldo_restante

    # Relatório Final
    df_result = pd.DataFrame(ativos_finais)
    df_result['Qtd'] = df_result['Valor_USDT'] / df_result['Preco']
    
    print(f"\n🛒 Sugestão de Carteira para {investimento:.2f} USDT...\n")
    cols = ['Ativo', 'Preco', 'Alvo_Venda', 'Upside_%', 'Valor_USDT', 'Qtd', 'Motivo']
    print(df_result[cols].to_string(index=False, formatters={
        'Preco': '{:,.4f}'.format,
        'Alvo_Venda': '{:,.4f}'.format,
        'Upside_%': '{:,.1f}%'.format,
        'Valor_USDT': '{:,.2f}'.format,
        'Qtd': '{:,.6f}'.format
    }))
    
    print("\n" + "-"*80)
    print("💡 ESTRATÉGIA DE SAÍDA:")
    print("- O 'Alvo_Venda' é projetado na recuperação de 50% do gap até o topo histórico.")
    print("- Isso representa um retorno à 'normalidade' antes da euforia final.")

if __name__ == "__main__":
    limites = obter_limites_binance()
    df_base = obter_dados_crypto()
    if not df_base.empty:
        df_step1 = stage_1_graham_crypto(df_base)
        if not df_step1.empty:
            df_step2 = stage_2_quality_buffett(df_step1)
            if not df_step2.empty:
                df_final = stage_3_ranking_lollapalooza(df_step2)
                montar_carteira_binance(df_final, limites)
            else:
                print("Nenhum ativo passou no filtro de qualidade (Buffett).")
        else:
            print("Nenhum ativo passou no filtro de segurança (Graham).")
