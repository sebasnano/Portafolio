# Portafolio de software y datos

Sitio estático en español centrado en soluciones de software y datos: backend, ingeniería de datos, automatización e infraestructura como soporte. La página de inicio lidera con la evidencia de ingeniería de datos verificada (integridad, distribución, volumen y calidad) y todo el contenido público se deriva de hechos verificados aplicando una frontera estricta de privacidad.

## Vista rápida

1. Abrir `index.html` directamente, o iniciar un servidor local:

   ```bash
   python3 -m http.server 8000
   ```

2. Abrir la dirección local mostrada por el servidor.
3. Recorrer la página principal, la metodología de evidencia, el perfil profesional y los casos bajo `casos/`.

## Validación local

Desde la raíz del repositorio, ejecutar:

```bash
python3 scripts/validate_site.py
```

El validador usa solo la biblioteca estándar de Python y revisa las páginas HTML públicas, sus enlaces y recursos locales, metadatos, estructura accesible, sitemap, `robots.txt` y marcadores de contenido incompleto. Los límites públicos examinados son `*.html`, `casos/*.html`, `assets/*.css`, `assets/*.svg`, `robots.txt` y `sitemap.xml`; el código del validador y del workflow queda fuera del escaneo de contenido. La misma comprobación se ejecuta en GitHub Actions para cada `push` y `pull_request`.

## Estructura

```text
.
├── CNAME
├── LICENSE
├── .gitignore
├── index.html
├── evidencia.html
├── perfil.html
├── robots.txt
├── sitemap.xml
├── scripts/
│   └── validate_site.py
├── .github/workflows/
│   └── validate-site.yml
├── assets/
│   ├── styles.css
│   ├── favicon.svg
│   └── social-card.png
└── casos/
    ├── workspace-local.html
    ├── workstation-mac.html
    ├── homelab-docker.html
    ├── proteccion-datos.html
    ├── data-lake.html
    └── ia-memoria.html
```

No requiere framework, gestor de paquetes ni proceso de build. Todos los enlaces internos son relativos para funcionar tanto en desarrollo local como bajo el subdirectorio de GitHub Pages.

La metodología pública de evidencia explica los estados, categorías, fechas, controles y límites de las afirmaciones. El perfil presenta una selección editorial del material profesional privado: organiza capacidades aplicadas, experiencia complementaria y áreas en profundización sin copiar la fuente extensa de forma literal.

## Mantenimiento

Checklist para agregar o actualizar una página de caso:

1. Partir de un caso existente como referencia y respetar las convenciones de la sección siguiente.
2. Completar los metadatos obligatorios: `lang`, título, descripción, canonical, Open Graph, Twitter Card y JSON-LD.
3. Agregar la URL canónica de la página a `sitemap.xml`.
4. Revisar el contenido contra las reglas de privacidad de este README antes de publicar.
5. Ejecutar `python3 scripts/validate_site.py` y corregir hasta que la validación pase.

## Convenciones de las páginas de caso

Las seis páginas de `casos/` comparten un andamiaje común que se mantiene por convención:

- Bloque de metadatos completo: descripción, canonical, Open Graph, Twitter Card y JSON-LD.
- Enlace de salto al contenido principal y navegación etiquetada.
- Tabla de contenidos con anclas internas válidas.
- Exactamente un `<main>` y un `<h1>` por página.
- Pie compartido con enlaces al perfil y a los demás casos.
- Enlaces internos relativos para funcionar en local y bajo GitHub Pages.

Estrategia de mantenimiento del andamiaje: la duplicación se gobierna con estas convenciones y la validación automática, sin introducir plantillas ni proceso de build. Un sistema de plantillas se reevaluará solo si la cantidad de páginas o la divergencia entre casos hiciera el costo de mantenimiento mayor que el de agregar una etapa de compilación.

## Reglas de contenido y privacidad

- Publicar solo hechos comprobados. Los únicos estados visibles son `Verificado`, `En progreso` y `Próximo`; los matices editoriales pertenecen a la prosa.
- Separar claims de implementación, instantánea, runtime y curaduría humana. Una implementación o instantánea no demuestra estado operativo actual.
- Fechar la evidencia junto al claim: `Verificado el DD/MM/AAAA` para implementación e instantáneas, y `Lectura operativa del DD/MM/AAAA` para runtime.
- No publicar direcciones de red, hostnames, usuarios, rutas internas ni identificadores operativos.
- No publicar nombres de contenedores, remotos, objetos, conjuntos de copias de seguridad ni horarios exactos.
- No incluir secretos, valores de entorno, credenciales, tokens, teléfonos o nombres de archivos personales.
- Describir repositorios privados y datos personales únicamente de forma general.
- Mantener diagramas con etiquetas genéricas y sanitizadas.
- Curar las fuentes privadas antes de publicar y conservar fuera del repositorio sus detalles operativos o personales.

## Política de reutilización

- El código fuente de este repositorio (`scripts/` y `.github/workflows/`) se distribuye bajo la licencia MIT incluida en `LICENSE`.
- El contenido escrito, las imágenes, la identidad visual y el material profesional del sitio quedan con todos los derechos reservados; su reutilización requiere autorización expresa.

## Compatibilidad de despliegue

El sitio puede publicarse directamente desde la raíz de la rama configurada en GitHub Pages. No se introducen dependencias externas ni una canalización de compilación; GitHub Actions solo valida los archivos y no despliega el sitio. `robots.txt` referencia `sitemap.xml`, que enumera las nueve URL canónicas. El CSS incluye estados de foco, diseño adaptable, preferencia de movimiento reducido y estilos de impresión para los casos de estudio.

Cada página declara una política de referencia y una CSP compatible con los estilos locales y los datos estructurados. GitHub Pages no permite configurar HSTS, `X-Content-Type-Options` ni `frame-ancestors` sin una capa edge; el sitio no agrega esa capa.
