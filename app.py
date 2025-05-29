from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
import pandas as pd
import ta

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

cache = {}
TEMPO_CACHE = timedelta(minutes=5)

def get_cache(key):
    if key in cache:
        valor, expiracao = cache[key]
        if datetime.now() < expiracao:
            logging.info(f"✅ Cache HIT: {key}")
            return valor
    return None

def set_cache(key, valor):
    cache[key] = (valor, datetime.now() + TEMPO_CACHE)
    logging.info(f"🆕 Cache SET: {key}")

def buscar(soup, label_esperado):
    label_esperado = label_esperado.lower()
    for td in soup.find_all("td"):
        texto = td.get_text(strip=True).lower()
        if label_esperado in texto:
            td_valor = td.find_next_sibling("td")
            if td_valor:
                valor_str = td_valor.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                try:
                    return float(valor_str)
                except:
                    logging.warning(f"⚠️ Erro ao converter '{td_valor.text.strip()}'")
                    return None
    logging.warning(f"❌ Indicador não encontrado: {label_esperado}")
    return None

def ajustar_por_perfil(recomendacao, pontos, perfil):
    if perfil == "conservador":
        if pontos >= 8:
            return "COMPRAR"
        elif pontos >= 6:
            return "MANTER"
        else:
            return "VENDER"
    elif perfil == "moderado":
        return recomendacao
    elif perfil == "agressivo":
        if pontos >= 6.5:
            return "COMPRAR"
        elif pontos >= 4.5:
            return "MANTER"
        else:
            return "VENDER"
    return recomendacao

@app.route('/')
def home():
    return {"mensagem": "API Bolsa com análise fundamentalista e técnica está online!"}

@app.route('/analise/acao/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    if ticker.upper().endswith("11"):
        return jsonify({"erro": "Este código termina com '11' e provavelmente é um Fundo Imobiliário. Use /analise/fii/."}), 400

    perfil = request.args.get("perfil", "moderado")
    cache_key = f"acao_{ticker.upper()}_{perfil}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        token = os.getenv("BRAPI_TOKEN")
        brapi_url = f"https://brapi.dev/api/quote/{ticker.upper()}"
        if token:
            brapi_url += f"?token={token}"
        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()
        if 'results' not in brapi_data or not brapi_data['results']:
            return jsonify({"erro": "Ticker não encontrado na Brapi."}), 404
        brapi_data = brapi_data['results'][0]

        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')
        pl = brapi_data.get('priceEarnings')
        crescimento_receita = brapi_data.get('earningsGrowth')
        valor_mercado = brapi_data.get("marketCap")

        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        indicadores = {
            "ticker": ticker.upper(),
            "empresa": empresa,
            "preco": preco,
            "P/L": pl,
            "Dividend Yield": buscar(soup, "Div. yield"),
            "ROE": buscar(soup, "ROE"),
            "ROIC": buscar(soup, "ROIC"),
            "EV/EBITDA": buscar(soup, "EV / EBITDA"),
            "Margem Líquida": buscar(soup, "Marg. líquida"),
            "Dívida/Patrimônio": buscar(soup, "Div br/ patrim"),
            "Crescimento de Receita": buscar(soup, "Cres. rec (5a)"),
            "Valor de Mercado": valor_mercado
        }

        pontos = 0
        explicacoes = []

        if pl and 5 <= pl <= 15:
            pontos += 1.5
            explicacoes.append("✅ P/L em faixa ideal (5-15)")
        if indicadores['ROE'] and indicadores['ROE'] > 10:
            pontos += 1
            explicacoes.append("✅ ROE acima de 10%")
        if indicadores['Dividend Yield'] and indicadores['Dividend Yield'] > 4:
            pontos += 1
            explicacoes.append("✅ Dividend Yield acima de 4%")
        if indicadores['EV/EBITDA'] and 0 < indicadores['EV/EBITDA'] < 8:
            pontos += 1
            explicacoes.append("✅ EV/EBITDA saudável")
        if indicadores['Margem Líquida'] and indicadores['Margem Líquida'] > 10:
            pontos += 1
            explicacoes.append("✅ Margem Líquida > 10%")
        if indicadores['Dívida/Patrimônio'] is not None and 0 <= indicadores['Dívida/Patrimônio'] < 1:
            pontos += 1
            explicacoes.append("✅ Dívida/Patrimônio < 1")
        if indicadores['ROIC'] and indicadores['ROIC'] > 8:
            pontos += 1
            explicacoes.append("✅ ROIC acima de 8%")
        if crescimento_receita and crescimento_receita > 0.05:
            pontos += 0.5
            explicacoes.append("✅ Crescimento de Receita > 5%")

        # Análise técnica com yfinance
        try:
            yf_ticker = yf.Ticker(ticker.upper() + ".SA")
            df = yf_ticker.history(period="6mo", interval="1d")
            df = ta.add_all_ta_features(df, open="Open", high="High", low="Low", close="Close", volume="Volume")
            rsi = df['momentum_rsi'].iloc[-1]
            mm200 = df['close'].rolling(window=200).mean().iloc[-1]
            preco_atual = df['close'].iloc[-1]
            if rsi < 30:
                pontos += 0.5
                explicacoes.append("✅ RSI < 30 (sobrevendido)")
            if preco_atual > mm200:
                pontos += 0.5
                explicacoes.append("✅ Acima da MM200")
        except:
            explicacoes.append("⚠️ Erro na análise técnica")

        if pl and pl > 60:
            recomendacao = "VENDER"
        elif pontos >= 8.5:
            recomendacao = "COMPRAR"
        elif pontos >= 6:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        recomendacao = ajustar_por_perfil(recomendacao, pontos, perfil)

        indicadores["Pontuacao"] = f"{round(pontos, 2)}/10"
        indicadores["Recomendacao"] = recomendacao
        indicadores["Explicacao"] = explicacoes

        set_cache(cache_key, indicadores)
        return jsonify(indicadores)

    except Exception as e:
        import traceback
        logging.error(f"Erro na análise da ação {ticker}: {e}")
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500
