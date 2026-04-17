#!/usr/bin/env python3
"""
Soluções Eventos - Sistema de Notas de Fechamento
Web App + Bot WhatsApp
"""

import os
import json
import tempfile
import base64
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template
from gerar_nota import gerar_nota

app = Flask(__name__)

# ── Configurações (via variáveis de ambiente) ────────────────────────────────
WHATSAPP_TOKEN      = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "solucoes_eventos_2024")
WHATSAPP_PHONE_ID   = os.environ.get("WHATSAPP_PHONE_ID", "")
DRIVE_FOLDER_ID     = os.environ.get("DRIVE_FOLDER_ID", "1GJRkSySrYFxCIxV8mOctxDc7HDG29Y_g")

# Sessões ativas do bot (em memória — suficiente para uso leve)
sessoes = {}

# ── Rota principal — formulário web ─────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── Gerar PDF via formulário web ─────────────────────────────────────────────
@app.route("/gerar", methods=["POST"])
def gerar():
    try:
        data = request.get_json()

        itens = []
        for item in data.get("itens", []):
            itens.append({
                "nome":       item["nome"],
                "valor_unit": float(item["valor_unit"]),
                "quant":      int(item["quant"]),
                "dias":       int(item.get("dias", 1)),
            })

        output_path = f"/tmp/Nota_{data['cliente'].replace(' ', '_')}_{data['num_evento']}.pdf"

        gerar_nota(
            cliente        = data["cliente"],
            evento         = data["evento"],
            local          = data["local"],
            data           = data["data"],
            num_evento     = data["num_evento"],
            num_pedido     = data["num_pedido"],
            itens          = itens,
            vencimento     = data["vencimento"],
            forma_pagamento= data.get("forma_pagamento", "PIX"),
            num_parcelas   = int(data.get("num_parcelas", 1)),
            output_path    = output_path,
        )

        # Tenta fazer upload pro Google Drive (opcional)
        drive_link = None
        try:
            drive_link = upload_drive(output_path, os.path.basename(output_path))
        except Exception as e:
            print(f"Drive upload falhou: {e}")

        return jsonify({
            "ok":         True,
            "filename":   os.path.basename(output_path),
            "drive_link": drive_link,
        })

    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/download/<filename>")
def download(filename):
    path = f"/tmp/{filename}"
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=filename)
    return "Arquivo não encontrado", 404


# ── Upload pro Google Drive ───────────────────────────────────────────────────
def upload_drive(filepath, filename):
    """Faz upload do PDF para a pasta 'Notas Soluções' no Google Drive."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        return None

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name":    filename,
        "parents": [DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(filepath, mimetype="application/pdf")
    f = service.files().create(body=file_metadata, media_body=media, fields="id,webViewLink").execute()
    return f.get("webViewLink")


# ── WhatsApp Webhook ──────────────────────────────────────────────────────────
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp():
    if request.method == "GET":
        # Verificação do webhook pela Meta
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    # Mensagem recebida
    try:
        body = request.get_json()
        entry   = body["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]

        if "messages" not in value:
            return "ok", 200

        msg      = value["messages"][0]
        from_num = msg["from"]
        texto    = msg.get("text", {}).get("body", "").strip()

        resposta = processar_mensagem(from_num, texto)
        if resposta:
            enviar_whatsapp(from_num, resposta)

    except Exception as e:
        print(f"Erro webhook: {e}")

    return "ok", 200


def processar_mensagem(numero, texto):
    """Máquina de estados simples para coleta dos dados da nota."""
    texto_lower = texto.lower()

    # Iniciar / reiniciar
    if texto_lower in ["oi", "olá", "ola", "nota", "nova nota", "gerar nota", "iniciar"]:
        sessoes[numero] = {"etapa": "cliente"}
        return (
            "👋 Olá! Vamos gerar uma Nota de Fechamento.\n\n"
            "1️⃣ Qual é o *nome do cliente*?"
        )

    if numero not in sessoes:
        return (
            "Olá! 👋 Para gerar uma nota, envie *oi* ou *nova nota*."
        )

    s = sessoes[numero]
    etapa = s.get("etapa")

    if etapa == "cliente":
        s["cliente"] = texto
        s["etapa"]   = "evento"
        return "2️⃣ Qual é o *nome do evento*?"

    elif etapa == "evento":
        s["evento"] = texto
        s["etapa"]  = "local"
        return "3️⃣ Qual é o *local* do evento?"

    elif etapa == "local":
        s["local"] = texto
        s["etapa"] = "data"
        return "4️⃣ Qual é a *data* do evento? (ex: 17/04/2026)"

    elif etapa == "data":
        s["data"]  = texto
        s["etapa"] = "num_evento"
        return "5️⃣ Qual é o *número do evento*? (ex: 130)"

    elif etapa == "num_evento":
        s["num_evento"] = texto
        s["num_pedido"] = f"{texto}-1"
        s["etapa"]      = "itens"
        s["itens"]      = []
        return (
            "6️⃣ Agora envie os *itens* do pedido, um por linha, no formato:\n\n"
            "`Nome - Valor - Quantidade`\n\n"
            "Exemplo:\n"
            "Bistro - 8,00 - 100\n"
            "Baldes - 1,00 - 200\n\n"
            "Quando terminar, envie *pronto*."
        )

    elif etapa == "itens":
        if texto_lower == "pronto":
            if not s["itens"]:
                return "⚠️ Adicione pelo menos um item antes de continuar."
            s["etapa"] = "vencimento"
            return "7️⃣ Qual é a *data de vencimento*? (ex: 30/04/2026)"
        else:
            # Parsear item: "Nome - 8,00 - 100"
            try:
                partes = [p.strip() for p in texto.split("-")]
                nome       = partes[0]
                valor_unit = float(partes[1].replace(",", "."))
                quant      = int(partes[2])
                s["itens"].append({"nome": nome, "valor_unit": valor_unit, "quant": quant, "dias": 1})
                return f"✅ Item adicionado: *{nome}* (R$ {partes[1]} x {quant})\nEnvie mais itens ou *pronto* para continuar."
            except:
                return "⚠️ Formato inválido. Use: `Nome - Valor - Quantidade`\nExemplo: `Bistro - 8,00 - 100`"

    elif etapa == "vencimento":
        s["vencimento"] = texto
        s["etapa"]      = "pagamento"
        return "8️⃣ Qual a *forma de pagamento*? (ex: PIX, Dinheiro, Cartão)"

    elif etapa == "pagamento":
        s["forma_pagamento"] = texto
        s["etapa"]           = "confirmacao"

        # Monta resumo
        resumo = (
            f"📋 *Resumo da Nota:*\n\n"
            f"👤 Cliente: {s['cliente']}\n"
            f"🎉 Evento: {s['evento']} - {s['local']}\n"
            f"📅 Data: {s['data']}\n"
            f"🔢 Nº Evento: {s['num_evento']}\n\n"
            f"*Itens:*\n"
        )
        total = 0
        for item in s["itens"]:
            sub    = item["valor_unit"] * item["quant"]
            total += sub
            resumo += f"• {item['nome']}: R$ {item['valor_unit']:.2f} x {item['quant']} = R$ {sub:.2f}\n"
        resumo += (
            f"\n💰 *Total: R$ {total:.2f}*\n"
            f"📆 Vencimento: {s['vencimento']}\n"
            f"💳 Pagamento: {s['forma_pagamento']}\n\n"
            f"Confirma? Responda *sim* para gerar ou *não* para cancelar."
        )
        return resumo

    elif etapa == "confirmacao":
        if texto_lower in ["sim", "s", "yes", "confirma", "confirmar"]:
            try:
                output_path = f"/tmp/Nota_{s['cliente'].replace(' ', '_')}_{s['num_evento']}.pdf"
                gerar_nota(
                    cliente        = s["cliente"],
                    evento         = s["evento"],
                    local          = s["local"],
                    data           = s["data"],
                    num_evento     = s["num_evento"],
                    num_pedido     = s["num_pedido"],
                    itens          = s["itens"],
                    vencimento     = s["vencimento"],
                    forma_pagamento= s["forma_pagamento"],
                    output_path    = output_path,
                )

                # Envia o PDF via WhatsApp
                enviar_pdf_whatsapp(numero, output_path, os.path.basename(output_path))

                # Tenta upload no Drive
                try:
                    link = upload_drive(output_path, os.path.basename(output_path))
                    if link:
                        enviar_whatsapp(numero, f"✅ Nota também salva no Google Drive:\n{link}")
                except:
                    pass

                del sessoes[numero]
                return None  # PDF já foi enviado

            except Exception as e:
                del sessoes[numero]
                return f"❌ Erro ao gerar nota: {str(e)}"

        elif texto_lower in ["não", "nao", "n", "no", "cancelar"]:
            del sessoes[numero]
            return "❌ Cancelado. Envie *nova nota* para começar de novo."
        else:
            return "Responda *sim* para confirmar ou *não* para cancelar."

    return "Não entendi. Envie *oi* para começar."


def enviar_whatsapp(para, mensagem):
    """Envia mensagem de texto via WhatsApp Cloud API."""
    import requests
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type":  "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to":   para,
        "type": "text",
        "text": {"body": mensagem},
    }
    requests.post(url, headers=headers, json=payload)


def enviar_pdf_whatsapp(para, filepath, filename):
    """Envia PDF como documento via WhatsApp Cloud API."""
    import requests

    # 1. Faz upload do arquivo para a API
    url_upload = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/media"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    with open(filepath, "rb") as f:
        files = {
            "file":              (filename, f, "application/pdf"),
            "messaging_product": (None, "whatsapp"),
            "type":              (None, "application/pdf"),
        }
        resp    = requests.post(url_upload, headers=headers, files=files)
        media_id = resp.json().get("id")

    if not media_id:
        enviar_whatsapp(para, "⚠️ Erro ao enviar o PDF. Tente novamente.")
        return

    # 2. Envia o documento
    url_msg  = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers2 = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload  = {
        "messaging_product": "whatsapp",
        "to":   para,
        "type": "document",
        "document": {
            "id":       media_id,
            "filename": filename,
            "caption":  "✅ Nota de Fechamento gerada com sucesso!",
        },
    }
    requests.post(url_msg, headers=headers2, json=payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
