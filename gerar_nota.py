#!/usr/bin/env python3
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

EMPRESA = {
    "nome": "Soluções Eventos",
    "cnpj": "52.454.829/0001-68",
    "endereco": "Rua Sotero dos Reis,77 - Praça da Bandeira,RJ - 20270-200",
    "pix_nome": "SL RIO EVENTOS",
    "pix_chave": "60600728000186",
    "pix_banco": "SANTANDER",
    "logo": os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.jpg"),
}

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_nota(cliente, evento, local, data, num_evento, num_pedido,
               itens, vencimento, forma_pagamento="PIX", num_parcelas=1,
               desconto=None, output_path=None):

    if output_path is None:
        output_path = f"/tmp/Nota_{cliente.replace(' ', '_')}_{num_evento}.pdf"

    total_bruto = sum(i["valor_unit"] * i["quant"] * i.get("dias", 1) for i in itens)
    total_final = total_bruto - (desconto or 0)

    estilo_normal = ParagraphStyle("Normal", fontName="Helvetica", fontSize=10, leading=14)
    estilo_bold   = ParagraphStyle("Bold",   fontName="Helvetica-Bold", fontSize=10, leading=14)
    estilo_titulo = ParagraphStyle("Titulo", fontName="Helvetica-Bold", fontSize=18, leading=22,
                                   alignment=TA_CENTER, spaceAfter=18)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=10*mm, bottomMargin=15*mm)
    story = []

    logo_img = Image(EMPRESA["logo"], width=28*mm, height=28*mm)
    header = Table([[
        logo_img,
        Paragraph(f"<b>{EMPRESA['nome']}</b><br/>{EMPRESA['cnpj']}<br/>{EMPRESA['endereco']}", estilo_normal),
        Paragraph(f"<b>Nº EVENTO:{num_evento}</b>", estilo_bold),
    ]], colWidths=[32*mm, 110*mm, 28*mm])
    header.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),1,colors.black),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.black),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(2,0),(2,0),"CENTER"),
        ("PADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(1,0),(1,0),8),
    ]))
    story.append(header)
    story.append(Spacer(1, 18*mm))
    story.append(Paragraph("NOTA DE FECHAMENTO", estilo_titulo))
    story.append(Spacer(1, 4*mm))

    def campo(label, valor):
        return Paragraph(f"<b>{label}</b> {valor}",
                         ParagraphStyle("c", fontName="Helvetica", fontSize=11, leading=16))

    story.append(campo("CLIENTE:", cliente))
    story.append(Spacer(1, 2*mm))
    story.append(campo("EVENTO:", f"{evento} - {local}"))
    story.append(Spacer(1, 2*mm))
    story.append(campo("DATA:", data))
    story.append(Spacer(1, 10*mm))

    cab = [Paragraph(f"PEDIDO Nº {num_pedido}",
                     ParagraphStyle("ph", fontName="Helvetica", fontSize=9)), "", "", "", ""]
    col_h = [
        Paragraph("<b>Nome/Descrição</b>",      ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9)),
        Paragraph("<b>Valor Unit.</b>",         ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER)),
        Paragraph("<b>Quant.</b>",              ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER)),
        Paragraph("<b>Nº de Dias</b>",          ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER)),
        Paragraph("<b>Valor Total</b>",         ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER)),
    ]
    linhas = [cab, col_h]
    for item in itens:
        dias = item.get("dias", 1)
        sub  = item["valor_unit"] * item["quant"] * dias
        linhas.append([
            Paragraph(f"<b>{item['nome']}</b>",          ParagraphStyle("td", fontName="Helvetica-Bold", fontSize=9)),
            Paragraph(formatar_moeda(item["valor_unit"]), ParagraphStyle("td", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
            Paragraph(str(item["quant"]),                 ParagraphStyle("td", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
            Paragraph(str(float(dias)),                   ParagraphStyle("td", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
            Paragraph(formatar_moeda(sub),                ParagraphStyle("td", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)),
        ])
    linhas.append([
        Paragraph("TOTAL", ParagraphStyle("tot", fontName="Helvetica", fontSize=9)),
        "", "", "",
        Paragraph(f"<b>{formatar_moeda(total_final)}</b>",
                  ParagraphStyle("tot", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT)),
    ])

    tabela = Table(linhas, colWidths=[75*mm, 28*mm, 22*mm, 24*mm, 28*mm])
    tabela.setStyle(TableStyle([
        ("SPAN",(0,0),(-1,0)), ("BOX",(0,0),(-1,0),0.5,colors.black),
        ("BOX",(0,1),(-1,1),0.5,colors.black), ("INNERGRID",(0,1),(-1,1),0.5,colors.black),
        ("BACKGROUND",(0,1),(-1,1),colors.Color(0.85,0.85,0.85)),
        ("BOX",(0,2),(-1,-2),0.5,colors.black), ("INNERGRID",(0,2),(-1,-2),0.5,colors.black),
        ("VALIGN",(0,2),(-1,-2),"MIDDLE"),
        ("BOX",(0,-1),(-1,-1),0.5,colors.black), ("SPAN",(0,-1),(3,-1)),
        ("PADDING",(0,0),(-1,-1),4),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("*O Valor total já está com o desconto aplicado",
                            ParagraphStyle("disc", fontName="Helvetica", fontSize=9, leading=12)))
    story.append(Spacer(1, 10*mm))

    pgto = Table([
        ["", "Vencimento", "Valor", "Forma de Pagamento"],
        [f"Em {num_parcelas} parcela{'s' if num_parcelas>1 else ''}", vencimento, formatar_moeda(total_final), forma_pagamento],
        ["", "", "", f"Valor Total {formatar_moeda(total_final)}"],
    ], colWidths=[30*mm, 40*mm, 40*mm, 63*mm])
    pgto.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.5,colors.black), ("INNERGRID",(0,0),(-1,-1),0.5,colors.black),
        ("BACKGROUND",(1,0),(-1,0),colors.Color(0.85,0.85,0.85)),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),9), ("ALIGN",(1,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("PADDING",(0,0),(-1,-1),5),
        ("SPAN",(0,1),(0,2)), ("FONTNAME",(-1,-1),(-1,-1),"Helvetica-Bold"),
    ]))
    story.append(pgto)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("<b>DADOS PARA PAGAMENTO:</b>",
                            ParagraphStyle("dp", fontName="Helvetica-Bold", fontSize=11, leading=16)))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(EMPRESA["pix_nome"], estilo_normal))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(f"PIX: {EMPRESA['pix_chave']}", estilo_normal))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(EMPRESA["pix_banco"], estilo_normal))

    doc.build(story)
    return output_path
