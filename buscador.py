import requests

MOUSER_API_KEY = "57a42680-6568-42ba-ae30-6ed72ea592fd"

def buscar_datos_componente(componente):
    componente_clean = componente.strip().upper()
    
    url = f"https://api.mouser.com/api/v1/search/partnumber?apiKey={MOUSER_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "SearchByPartRequest": {
            "mouserPartNumber": componente_clean,
            "partSearchOptions": "string"
        }
    }
    
    try:
        respuesta = requests.post(url, json=payload, headers=headers, timeout=10)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            parts = datos.get("SearchResults", {}).get("Parts", [])
            
            if not parts:
                return None
                
            part = parts[0]
            
            # Guardamos solo lo importante en un diccionario limpio
            info_componente = {
                "modelo": componente_clean,
                "fabricante": part.get("Manufacturer", "No especificado"),
                "descripcion": part.get("Description", "No especificada"),
                "encapsulado": part.get("PackageCase", "No especificado"),
                "atributos": []
            }
            
            # Sumamos los detalles técnicos (voltaje, corriente, etc.)
            specs = part.get("ProductAttributes", [])
            for spec in specs:
                nombre = spec.get("AttributeName", "")
                valor = spec.get("AttributeValue", "")
                if nombre and valor:
                    info_componente["atributos"].append(f"{nombre}: {valor}")
                    
            return info_componente
        return None
    except:
        return None