from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

# Cache simples
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
        if pontos >= 7.5:
            return "COMPRAR"
        elif pontos >= 5:
            return "MANTER"
        else:
            return "VENDER"
    elif perfil == "moderado":
        return recomendacao
    elif perfil == "agressivo":
        if pontos >= 6:
            return "COMPRAR"
        elif pontos >= 3.5:
            return "MANTER"
        else:
            return "VENDER"
    return recomendacao

@app.route('/')
def home():
    return {"mensagem": "API Bolsa está online!"}

@app.route('/analise/acao/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    if ticker.upper().endswith("11"):
        return jsonify({"erro": "Este código termina com '11' e provavelmente é um Fundo Imobiliário. Use /analise/fii/."}), 400

    perfil = request.args.get("perfil", "moderado")

    cache_key = f"acao_{ticker.upper()}"
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
            explicacoes.append("✅ P/L ideal entre 5 e 15")
        else:
            explicacoes.append("⚠️ P/L fora da faixa ideal")

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
            explicacoes.append("✅ Margem Líquida maior que 10%")

        if indicadores['Dívida/Patrimônio'] is not None and 0 <= indicadores['Dívida/Patrimônio'] < 1:
            pontos += 1
            explicacoes.append("✅ Dívida/Patrimônio saudável")

        if indicadores['ROIC'] and indicadores['ROIC'] > 8:
            pontos += 1
            explicacoes.append("✅ ROIC acima de 8%")

        if crescimento_receita:
            if crescimento_receita > 0.05:
                pontos += 0.5
                explicacoes.append("✅ Crescimento de receita acima de 5%")

        if pl and pl > 60:
            recomendacao = "VENDER"
        elif pontos >= 7:
            recomendacao = "COMPRAR"
        elif pontos >= 4:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        recomendacao = ajustar_por_perfil(recomendacao, pontos, perfil)

        indicadores["Pontuacao"] = f"{round(pontos, 2)}/8"
        indicadores["Recomendacao"] = recomendacao
        indicadores["Explicacao"] = explicacoes
        indicadores["Perfil"] = perfil

        set_cache(cache_key, indicadores)
        return jsonify(indicadores)

    except Exception as e:
        import traceback
        logging.error(f"Erro na análise da ação {ticker}: {e}")
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500

@app.route('/analise/fii/<ticker>', methods=['GET'])
def analisar_fii(ticker):
    if not ticker.upper().endswith("11"):
        return jsonify({"erro": "Este código não termina com '11'. Provavelmente é uma ação. Use /analise/acao/."}), 400

    perfil = request.args.get("perfil", "moderado")

    cache_key = f"fii_{ticker.upper()}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        preco = buscar(soup, "Cotação")
        dy = buscar(soup, "Div. yield")
        pvp = buscar(soup, "P/VP")
        caprate = buscar(soup, "Cap rate")
        vacancia = buscar(soup, "Vacância média")
        liquidez = buscar(soup, "Vol $ méd")
        hist = buscar(soup, "Dividendo/cota")

        pontos = 0
        explicacoes = []

        if dy and dy > 7:
            pontos += 1.5
            explicacoes.append("✅ Dividend Yield acima de 7%")

        if pvp and pvp < 1.05:
            pontos += 1
            explicacoes.append("✅ P/VP abaixo de 1.05")

        if caprate and caprate > 8:
            pontos += 1
            explicacoes.append("✅ Cap Rate acima de 8%")

        if vacancia is not None and vacancia < 10:
            pontos += 1
            explicacoes.append("✅ Vacância abaixo de 10%")

        if liquidez and liquidez > 500:
            pontos += 0.75
            explicacoes.append("✅ Boa liquidez média diária")

        if hist and hist > 0.9:
            pontos += 0.75
            explicacoes.append("✅ Histórico de dividendos consistente")

        if dy and dy < 5 or (vacancia and vacancia > 25) or caprate == 0:
            recomendacao = "VENDER"
        elif pontos >= 5:
            recomendacao = "COMPRAR"
        elif pontos >= 3.5:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        recomendacao = ajustar_por_perfil(recomendacao, pontos, perfil)

        resultado = {
            "ticker": ticker.upper(),
            "empresa": f"FII {ticker.upper()}",
            "preco": preco,
            "Dividend Yield": dy,
            "P/VP": pvp,
            "Vacância": vacancia,
            "Cap Rate": caprate,
            "Liquidez Média": liquidez,
            "Histórico de Dividendos": hist,
            "Pontuacao": f"{round(pontos, 2)}/6",
            "Recomendacao": recomendacao,
            "Explicacao": explicacoes,
            "Perfil": perfil
        }

        set_cache(cache_key, resultado)
        return jsonify(resultado)

    except Exception as e:
        import traceback
        logging.error(f"Erro na análise do FII {ticker}: {e}")
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
