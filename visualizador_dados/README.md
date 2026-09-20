# Visualizador dos dados originais

Interface estática para explorar as tabelas 4714, 6803, 6805 e 6892 do
SIDRA/IBGE. Os CSVs da camada `raw` são apenas lidos e não são modificados.

## Como executar

Na raiz do projeto, com o ambiente virtual ativado, execute:

```bash
python -m http.server 8000
```

Sem ativar o ambiente virtual, use:

```bash
venv/bin/python -m http.server 8000
```

Em seguida, abra no navegador:

```text
http://localhost:8000/visualizador_dados/
```

Não abra o `index.html` diretamente com `file://`, pois navegadores bloqueiam a
leitura dos CSVs locais por segurança.

## Recursos

- uma visualização colorida para cada CSV;
- busca em todos os campos;
- filtros de nível territorial e categoria;
- ordenação por qualquer coluna;
- paginação configurável;
- destaque para códigos, valores e símbolos especiais;
- resumo de registros, municípios, categorias e qualidade;
- exportação da visão filtrada em CSV;
- layout adaptável para computador e celular.

É possível abrir uma tabela diretamente pelo endereço:

```text
http://localhost:8000/visualizador_dados/?tabela=6805
```
