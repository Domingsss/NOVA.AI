import sys
import time
sys.path.append('.')

print("=== Teste 1: qual pacote está instalado? ===")
DDGS = None
pacote = None
try:
    from ddgs import DDGS
    pacote = "ddgs (novo)"
    print(f"✅ Pacote novo 'ddgs' disponível")
except ImportError:
    try:
        from duckduckgo_search import DDGS
        pacote = "duckduckgo_search (antigo)"
        print(f"⚠️ Só o pacote antigo 'duckduckgo_search' disponível")
    except ImportError:
        print("❌ NENHUM pacote instalado!")
        sys.exit(1)

print(f"\n=== Teste 2: busca (pacote: {pacote}) ===")
try:
    ddgs = DDGS()
    print("Objeto DDGS criado. Tentando busca...")
    
    queries = ["Python", "Brasil", "tecnologia 2025"]
    for q in queries:
        try:
            resultados = list(ddgs.text(q, max_results=3))
            print(f"  Query '{q}': {len(resultados)} resultados")
            if resultados:
                print(f"    Primeiro: {resultados[0].get('title', 'sem título')}")
                break
            time.sleep(1)
        except Exception as e:
            print(f"  Query '{q}': ERRO - {e}")
            
except Exception as e:
    print(f"❌ Erro ao criar DDGS: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Teste 3: tipo do retorno ===")
try:
    ddgs = DDGS()
    r = ddgs.text("teste", max_results=1)
    print(f"Tipo: {type(r)}")
    r_list = list(r)
    if r_list:
        print(f"Keys do primeiro resultado: {list(r_list[0].keys())}")
        print(f"Resultado completo: {r_list[0]}")
    else:
        print("Lista vazia")
except Exception as e:
    print(f"❌ {e}")