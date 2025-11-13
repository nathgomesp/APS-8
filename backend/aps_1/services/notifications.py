import firebase_admin
from firebase_admin import credentials, messaging

# Inicializa o Firebase com a chave da conta de serviço
# Certifique-se de que o caminho para o JSON está correto no seu projeto
cred = credentials.Certificate("services/aps1-7b3d9-08e66354e0ff.json")
firebase_admin.initialize_app(cred)

# Envia notificação push via Firebase Cloud Messaging (API v1)
def send_push_notification(token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=token,
    )
    try:
        response = messaging.send(message)
        print(f"Notificação enviada com sucesso: {response}")
        return True
    except Exception as e:
        print(f"Erro ao enviar notificação: {e}")
        return False

# Gera recomendações de saúde com base no nível de poluição (AQI)
def get_health_recommendations(aqi):
    """
    Faixas baseadas em categorias comuns de AQI:
      0-50     Good (Bom)
      51-100   Moderate (Moderado)
      101-150  Unhealthy for Sensitive Groups (Ruim para grupos sensíveis)
      151-200  Unhealthy (Ruim)
      201-300  Very Unhealthy (Muito ruim)
      301+     Hazardous (Perigoso)
    Retorna uma lista de recomendações adequadas à faixa.
    """
    try:
        aqi_value = int(aqi)
    except Exception:
        aqi_value = 0

    if aqi_value <= 50:
        return [
            "Qualidade do ar boa — atividades ao ar livre são seguras.",
            "Continue ventilando ambientes quando apropriado.",
            "Mantenha hábitos saudáveis."
        ]
    elif aqi_value <= 100:
        return [
            "Qualidade do ar moderada — pessoas sensíveis podem notar sintomas leves.",
            "Se você tem problemas respiratórios, evite exercícios extenuantes ao ar livre.",
            "Considere monitorar sintomas e reduzir exposição prolongada."
        ]
    elif aqi_value <= 150:
        return [
            "Ruim para grupos sensíveis — crianças, idosos e pessoas com doenças respiratórias devem ter cuidado.",
            "Evite exercícios vigorosos ao ar livre.",
            "Mantenha portas e janelas fechadas quando possível.",
            "Considere o uso de máscara PFF2 em saídas necessárias."
        ]
    elif aqi_value <= 200:
        return [
            "Ruim — sintomas mais prováveis em indivíduos sensíveis e também em pessoas saudáveis.",
            "Minimize atividades físicas ao ar livre.",
            "Use máscara PFF2 ou equivalente se precisar sair.",
            "Mantenha ambientes internos com ar mais puro (purificador, ar-condicionado com filtros)."
        ]
    elif aqi_value <= 300:
        return [
            "Muito ruim — risco elevado para toda a população.",
            "Evite sair de casa, especialmente crianças, idosos e pessoas com doenças respiratórias ou cardíacas.",
            "Se precisar sair, use proteção respiratória adequada e reduza o tempo de exposição.",
            "Considere procurar locais com ar filtrado e consulte um profissional de saúde se surgir piora."
        ]
    else:  # aqi_value > 300
        return [
            "Perigoso — condições ameaçam a saúde de todos.",
            "Permanecer em ambientes fechados com ar limpo é altamente recomendado.",
            "Se houver necessidade de sair, utilize equipamento de proteção respiratória certificado (máscara PFF2/N95).",
            "Procure atendimento médico se apresentar sintomas graves como falta de ar ou dor no peito."
        ]
