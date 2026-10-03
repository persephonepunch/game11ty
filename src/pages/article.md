---
layout: "kb.njk"
kicker: "Reference"
status: "Living reference · Image, 3D and video metadata"
scope: "How descriptions and rights travel with media files, from alt text to XMP, glTF and video posters."
markdownUrl: "/docs/alt-xmp-favicons.md"
sourceUrl: "https://github.com/persephonepunch/game11ty/blob/main/src/pages/article.md"
pdfUrl: "/docs/gamestreaming-xmpdata.pdf"
ogImage: "/docs/og-mediaxmp.jpg"
heroImage: "/docs/mediaxmp-board.jpg"
summary: "Machines decide what an image shows, and who owns it, from three sources: the page's alt text, the XMP inside the file, and JSON-LD. This reference shows how to keep all three in agreement across JPG, PNG and WebP, favicons, 3D glTF models and video, and where exporters, encoders and compression break them. It's built on measurements from the game11ty site and the CLO jacket models, with Python and exiftool commands you can run yourself."
ogImageAlt: "Build board for the article: screenshots of the game11ty GitHub repo, the OMEN x Valorant page, code previews, game stream captures, CLO 3D and Adobe metadata dialogs, favicons and XMP data notes"
permalink: "/article/"
title: "ALT, XMP and Favicons: Image Metadata for Rights and Media Management"
description: "How alt text, embedded XMP and favicons carry descriptions and rights for search engines, DAMs and AI models, with JPG, PNG, WebP, glTF and Draco examples."
templateEngineOverride: md
---
Search engines, asset managers and AI models decide what an image shows, and who controls it, from text: the `alt` attribute, the metadata inside the file, and structured data on the page. When those three agree, a machine doesn't have to guess. When they're missing or contradict each other, it guesses, and the guess travels with the image into indexes, datasets and model outputs.

This article explains each layer, the Adobe XMP standard behind embedded metadata, how it's stored in JPG, PNG and WebP, and how rights fields act as a lightweight form of DRM. It ends with a worked example, the game11ty site, and a checklist for agencies and media teams.


## Three layers, one description

An image on the web can be described in three places. Each is read by different machines, and only one of them travels with the file.

| Layer | Where it lives | Who reads it | Survives a download? |
| --- | --- | --- | --- |
| HTML `alt` | The `<img>` tag on the page | Screen readers, search crawlers, AI models that read the page | No: it stays on the page |
| Embedded XMP | Inside the image file's bytes | DAMs, Google Images, scrapers, AI training pipelines | Yes, unless a tool strips it |
| schema.org JSON-LD | A `<script type="application/ld+json">` block on the page | Search engines, knowledge graphs | No: it stays on the page |

The page layers describe the image *in context*: what it's doing on this page. XMP describes the image *as an object*: what it shows and who owns it, wherever it ends up. Write the same description into all three. A crawler that reads the page and a pipeline that only ever sees the file then reach the same answer.

## The Adobe XMP standard

XMP (Extensible Metadata Platform) is Adobe's metadata format, standardised as ISO 16684-1. An XMP block is an RDF/XML document wrapped in an `<x:xmpmeta>` element and stored inside the file as a *packet*. Every Adobe app reads and writes it, and so do exiftool, DAMs and most image libraries.

Each field belongs to a namespace, and the prefix says who defined it. These are the ones that matter for description and rights, with the names the [IPTC Photo Metadata Standard 2025.1](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html) gives them:

| Field (IPTC name) | XMP property | What it holds |
| --- | --- | --- |
| Alt Text (Accessibility) | `Iptc4xmpCore:AltTextAccessibility` | Short description, the same as the HTML `alt` |
| Extended Description (Accessibility) | `Iptc4xmpCore:ExtDescrAccessibility` | Longer description for complex images |
| Description | `dc:description` | General caption |
| Creator | `dc:creator` | Person or organisation that made it |
| Copyright Notice | `dc:rights` | The copyright line |
| Credit Line | `photoshop:Credit` | How to credit it when published |
| Web Statement of Rights | `xmpRights:WebStatement` | URL of the rights or licence page |
| Licensor URL | `plus:Licensor` → `LicensorURL` | Where to license it |
| Data Mining | `plus:DataMining` | Whether data mining and AI/ML training are allowed |
| Digital Source Type | `Iptc4xmpExt:DigitalSourceType` | How it was made: camera, composite, AI-generated |
| Edit history | `xmpMM:History` | Which software saved it, and when |

The packet looks like this. It's from the game11ty share image, trimmed:

```xml
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:Iptc4xmpCore="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"
    xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/">
   <dc:description><rdf:Alt><rdf:li xml:lang="x-default">Inside the OMEN 35L Valorant special edition desktop…</rdf:li></rdf:Alt></dc:description>
   <Iptc4xmpCore:AltTextAccessibility><rdf:Alt><rdf:li xml:lang="x-default">Inside the OMEN 35L…</rdf:li></rdf:Alt></Iptc4xmpCore:AltTextAccessibility>
   <xmpRights:Marked>True</xmpRights:Marked>
   <xmpRights:WebStatement>https://persephonepunch.github.io/game11ty/rights/</xmpRights:WebStatement>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
```

Text fields are `rdf:Alt` lists keyed by `xml:lang`, so one file can carry alt text in several languages. Because the packet is RDF, a parser gets subject–property–value triples, not loose strings.

## Where XMP lives in JPG, PNG and WebP

The XMP packet is the same in every format. Only its container changes: each format has its own slot for it, next to (not inside) the pixel data.

| Format | Slot for XMP | How to recognise it | Also carries |
| --- | --- | --- | --- |
| JPG | `APP1` segment (marker `FF E1`) before the image data | Starts with `http://ns.adobe.com/xap/1.0/` + a null byte | EXIF in another `APP1`, legacy IPTC in `APP13`, colour profile in `APP2` |
| PNG | `iTXt` text chunk | Keyword `XML:com.adobe.xmp` | EXIF in an `eXIf` chunk |
| WebP | ` XMP  ` chunk (the fourth character is a space) in the RIFF container | The `VP8X` header's XMP flag must be set ([spec](https://developers.google.com/speed/webp/docs/riff_container)) | EXIF in an `EXIF` chunk |

I read these slots directly from the game11ty files: every JPG has its XMP in `APP1` and every PNG in `iTXt:XML:com.adobe.xmp`. The share image also has a legacy IPTC `APP13` block, which exiftool keeps in sync with the XMP so older tools see the same copyright.

Because the metadata sits beside the pixels, any tool that re-encodes an image can drop it without changing how the image looks. The usual culprits are image CDNs and optimisers that convert to WebP or AVIF, social platforms, and "export for web" presets set to *None*. A rule of thumb: whenever an image passes through a tool, check that the rights fields came out the other side.

## How Python reads it: scraping as a semantic breakdown

Scraping a page isn't copying it. A scraper breaks the rendered page into roles: this is a heading, this is an image, this is its description, this block is structured data. The pixels arrive as opaque bytes, and the only thing they can say about themselves is their XMP. So a scraper ends up with two sources of meaning for every image: what the page says about it, and what the file says about itself.

The script below reads all three layers for every image on the live game11ty page, using `requests`, BeautifulSoup and the standard XML parser:

```python
import json, re, requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE = "https://persephonepunch.github.io/game11ty/"
NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "dc": "http://purl.org/dc/elements/1.1/",
      "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
      "xmpRights": "http://ns.adobe.com/xap/1.0/rights/"}

def xmp(data: bytes) -> dict:
    """Find the XMP packet in JPG/PNG/WebP bytes and read it as RDF."""
    m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.S)
    if not m:
        return {}
    descs = ET.fromstring(m.group()).findall(".//rdf:Description", NS)
    def text(prop):                     # a property can sit in any Description,
        pre, name = prop.split(":")     # as an element or as an attribute
        for d in descs:
            el = d.find(prop, NS)
            if el is not None:
                li = el.find(".//rdf:li", NS)
                return (li if li is not None else el).text
            if d.get(f"{{{NS[pre]}}}{name}"):
                return d.get(f"{{{NS[pre]}}}{name}")
    return {"alt": text("Iptc4xmpCore:AltTextAccessibility"),
            "rights": text("dc:rights"),
            "webStatement": text("xmpRights:WebStatement")}

soup = BeautifulSoup(requests.get(PAGE).text, "html.parser")
ld = {o["contentUrl"]: o for s in soup.find_all("script", type="application/ld+json")
      for o in json.loads(s.string).get("@graph", [])}

for img in soup.find_all("img"):
    url = urljoin(PAGE, img["src"])
    page_alt = img.get("alt")                   # layer 1: the page
    file_meta = xmp(requests.get(url).content)  # layer 2: the pixels' own XMP
    graph = ld.get(url, {})                     # layer 3: JSON-LD
```

Run against the live site on 3 October 2026, it found all three layers on every one of the 8 raster images, with matching descriptions and a rights URL in each file.

Two things in this code generalise to any metadata parser:

- **Treat XMP as RDF, not text.** The same property can be written as an element or an attribute, and exiftool spreads properties across several `rdf:Description` blocks, one per namespace. My first version read only the first block and reported every rights field as missing.
- **The page and the file are read separately.** `img.get("alt")` comes from the DOM; `xmp()` comes from bytes fetched on their own. A dataset built from downloaded images only ever sees the second.

## Optimization and bit size

Across the 15 images on game11ty, metadata adds 56 KB to 4.1 MB, or 1.4%. That cost is fixed per file, not per pixel, so it barely registers on large photos and dominates small icons. These are the measured figures:

| File | Size | Metadata | Share |
| --- | --- | --- | --- |
| HyperX hero PNG, 2880 px wide | 2,031 KB | 3.4 KB | 0.2% |
| OMEN desktop PNG | 633 KB | 3.5 KB | 0.6% |
| Gear photo JPG | 160 KB | 5.2 KB | 3.2% |
| Share image JPG | 99 KB | 7.1 KB | 7.1% |
| 32 px favicon PNG | 5.3 KB | 2.5 KB | 47% |
| Red emblem PNG | 6.1 KB | 3.8 KB | 63% |

Three things shape that cost:

- **Padding.** Adobe tools and exiftool leave empty space inside a JPEG's XMP packet so it can be edited later without rewriting the file. In the share image that padding is 2,498 bytes, about 40% of its packet. The PNG packets carry only 74 bytes.
- **Edit history.** `xmpMM:History` and document IDs record every save. They are useful in a DAM and dead weight on the web.
- **What you actually need.** Stripping the 32 px favicon to bare pixels gives 2,821 bytes; adding back only alt text, copyright and the rights URL gives 3,818. A minimal rights set costs about 1 KB.

**Frame load.** In both JPG and PNG the metadata sits *before* the pixel data: the `APP` segments come before the JPEG scan, and the `iTXt` chunk came before `IDAT` in every PNG checked. A browser decodes nothing until those bytes have arrived, so on a slow connection every kilobyte of metadata delays the first painted row. All four JPGs here are *baseline*, which decode top to bottom as bytes arrive; a *progressive* JPEG paints a coarse full frame first. Either way, a lean packet means the first pixels arrive sooner.

**Bit depth.** Every PNG here is 8 bits per channel. A 16-bit PNG doubles the pixel data and adds nothing a screen can show, so check for it before worrying about metadata.

**Conversion strips by default.** Converting the 101 KB gear photo to WebP with Google's `cwebp` gave 28 KB and **no metadata at all**: the alt text and rights were gone. With `-metadata xmp` the result was 33 KB and both survived. Other encoders and optimisers, including Rust-based tools such as `oxipng`, also drop metadata unless told to keep it, so set the keep option explicitly in your build.

**Rust and the pixel buffer.** When Rust handles an image, it works on a *pixel buffer*: an array of integer channel values, usually one unsigned byte (`u8`, 0–255) per red, green, blue and alpha channel. Each stage has its own name:

| Stage | Term | In Rust |
| --- | --- | --- |
| Reading a JPG, PNG or WebP into pixel values | Image decoding; *memory-safe decoding* when done in Rust | The compiler's ownership and bounds checks rule out the buffer overflows that C decoders are prone to |
| Holding the values in memory | Pixel buffer or framebuffer | `ImageBuffer` of `Rgba<u8>` in the `image` crate |
| Storing each channel as a whole number | Integer pixel format | `u8` per channel; `u16` or `f32` for higher bit depth |
| Turning shapes or 3D geometry into pixels | Rasterization; *software rendering* on the CPU | Fills the buffer directly |
| Painting a `<canvas>` on each frame from WebAssembly | Rendering into WASM linear memory | Rust writes the bytes, JavaScript passes them to the canvas as `ImageData`; *zero-copy* when no copy is made |

None of these stages handles XMP. The metadata sits beside the pixel data, so a pipeline that decodes to a pixel buffer and encodes again keeps only the pixels, as the `cwebp` test showed. A Rust image pipeline has to read the XMP before decoding and write it back after encoding, or the rights are lost at the first conversion.

## Security note

**Pixels and tokens.** Images and text are split into discrete integer units before a model uses them. A pixel stores brightness (0–255 per channel); a token stores a vocabulary index. Inside a model both become embedding vectors, which is how multimodal models compare images and language. Rust is common in the pipeline, including Hugging Face's tokenizers, because its compiler enforces memory safety.

**Parsers are the attack surface.** Many decoders for SVG and 3D models (glTF, Draco, OBJ, FBX) are written in C or C++, and a malformed file can exploit a memory bug in them. SVG can also carry scripts. Protect these files on three layers:

- **Code:** parse untrusted files with memory-safe code such as Rust, or sandbox C/C++ decoders.
- **Content:** sign assets (e.g. C2PA) to prove owner and integrity. XMP rights fields can be edited, so they aren't proof.
- **Transit:** serve over TLS. It protects files in transit only, so it complements signing.

AI agents should check signatures and rights before trusting a file.

**Higher-risk assets.** DAM libraries, 3D models and firmware need extra care: verify by hash or signature, restrict publishing, scan before processing, and install firmware only with a valid signature (secure boot).

## Release scan

game11ty now gates every deploy on an asset scan. [`asset_scan.py`](https://github.com/persephonepunch/game11ty/blob/main/scripts/asset_scan.py) runs in a throwaway Docker container with no network, a read-only file system and no secrets, so a hostile file has nothing to reach. The site only builds if the scan passes.

| Asset | What it checks |
| --- | --- |
| Every file | Real type matches the extension, read from the file's first bytes (its "magic bytes", e.g. `89 50 4E 47` = PNG); no executables, even disguised |
| JPG / PNG / WebP | Valid file structure; rights XMP present (`WebStatement`, alt text) |
| SVG | Valid XML; no `<script>`, `on…=` handlers, `javascript:` links, `<foreignObject>`, external URLs or XML entities |
| glTF / GLB | Header and chunks valid; every bufferView and accessor inside its data; buffer paths can't escape the model folder; `asset.copyright` set and not an exporter's default |
| PDF | No JavaScript, auto-run, launch or embedded-file actions |

On a test set of deliberately bad files it caught all 13 planted problems: a PNG renamed `.jpg`, an executable named `.png`, an image with no rights data, a hostile SVG, a PDF with auto-running JavaScript, and a GLB doctored so its data pointers run past the end of the file. The real CLO avatar fails too, on Stager's "2025 (c) Adobe Inc." copyright, which is the point: it shouldn't ship with that claim.

After the build, CI publishes [`asset-manifest.json`](/asset-manifest.json), a SHA-256 hash of every released file, so a download can be checked against what was scanned.

The lesson behind it is the security note's. In the July 2026 OpenAI–Hugging Face incident, the way in was a flaw in an HDF5 dataset parser running with access to credentials ([Wikipedia](https://en.wikipedia.org/wiki/OpenAI%E2%80%93HuggingFace_incident)). The scan parses untrusted files where nothing can be reached, and treats a file whose content doesn't match its label as an error. Run it locally with `python3 scripts/asset_scan.py src`.

## Rights metadata as lightweight DRM

XMP rights fields don't lock an image; they declare who owns it and on what terms, in a form machines act on. Real DRM encrypts content. Rights metadata is closer to a label that travels with the file: it can be stripped, but a crawler, DAM or training pipeline that respects it can read the terms without a human.

What each machine does with it:

- **Google Images** shows a *Licensable* badge when an image has a Web Statement of Rights (`xmpRights:WebStatement`). It also reads Creator, Credit Line, Copyright Notice, Licensor URL and Digital Source Type. Where XMP and the page's structured data disagree, Google uses the structured data ([Google Search Central](https://developers.google.com/search/docs/appearance/structured-data/image-license-metadata)).
- **AI and data-mining pipelines** can read `plus:DataMining`. Its controlled values include *Prohibited*, *Allowed*, and *Prohibited except for search engine indexing*, which the IPTC says rules out other uses such as AI/ML training ([IPTC 2025.1](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html)).
- **DAMs** index the full packet, so rights and usage terms show up in search and on download.

For agencies, the minimum useful set is: Copyright Notice, Creator, Credit Line, Web Statement of Rights pointing to a real licence page, Licensor URL, and a Data Mining value. Put the same licence URL in the page's JSON-LD (`license`, `acquireLicensePage`) so both readers agree.

**Content Credentials go a step further.** Photoshop's export dialog now has a *Content Credentials (Beta)* panel. These are cryptographically signed provenance records (the C2PA standard), so a reader can tell if they were tampered with, which plain XMP can't show. They complement XMP rather than replacing it.

## Favicons

A favicon is the most widely copied image a site has. It appears in tabs, bookmarks, search results and home screens, so it carries the brand further than any page image. Google requires it to be square and at least 8×8 px, recommends larger than 48×48, and accepts ICO, PNG, JPEG, GIF, BMP and TIFF ([Google Search Central](https://developers.google.com/search/docs/appearance/favicon-in-search)).

| Size | Used for | Best format |
| --- | --- | --- |
| 16, 32, 48 px | Browser tabs, `/favicon.ico` fallback | ICO holding all three, plus a 32 px PNG |
| 180 px | iPhone and iPad home screen (`apple-touch-icon`) | PNG |
| 192 px | Android home screen | PNG |
| 512 px | App install and splash screens | PNG, from a 512 px or larger source |

**PNG over JPG.** JPG has no transparency, so a JPG icon always sits on a solid square. Webflow handles this for you: the icons it generated for game11ty were real RGBA PNGs, even though their file names end in `.jpg`. Declare each one with an accurate `type` and `sizes`, and serve the real extension so the server sends the right content type.

**Upscaling costs.** Webflow made the 512 px icon by enlarging a 256 px source. The result is 355 KB, against 5 KB for the 32 px icon, and it looks soft at full size. Start from the largest size you need.

**Brand permission.** game11ty first shipped HyperX's logo as its favicon, copied over by the Webflow sync. Because a favicon is shown so widely, a third-party logo there implies an endorsement. It was replaced with an original crop with no logo.

**Metadata on icons.** Rights XMP on a 32 px icon is 47% of the file. That's still only about 2.5 KB, and icons are the images most often lifted, so keep a minimal set: alt text, copyright and the rights URL.

## Case study: game11ty

[game11ty](https://persephonepunch.github.io/game11ty/) is a one-page OMEN x Valorant site designed in Webflow, converted to static Eleventy pages by a Python script, and published on GitHub Pages. It was built on 3 October 2026, and the alt text, XMP and favicon work all happened that day.

![Pipeline diagram: the Webflow site feeds sync.py, which feeds postsync.py; images.json feeds postsync.py; postsync.py feeds the Eleventy build, which deploys to GitHub Pages](/docs/pipeline-diagram.png)

`sync.py` regenerates the templates from Webflow on every run, so anything added on top would be lost. `postsync.py` re-applies it from one file, `images.json`, which holds a single description per image. That one source is what keeps the three layers in agreement.

| Check | Before | After |
| --- | --- | --- |
| Images with XMP | 6 of 12, mostly tool names and IDs | All 9 page images, 5 favicons and the PDF |
| Images with an XMP alt text | 1, describing a laptop when the photo shows a desktop | All 9, matching the page |
| Rights fields (copyright, WebStatement, LicensorURL) | None | Every file, linking to a [rights page](https://persephonepunch.github.io/game11ty/rights/) |
| HTML `alt` accuracy | 2 wrong: the OMEN logo labelled "Valorant Champions", one photo given another's caption | All 9 corrected |
| JSON-LD `ImageObject` | None | 10 entries with description, licence and copyright |
| Favicon | HyperX logo, JPG declared as `image/x-icon` | Original icon, 5 PNG sizes plus `favicon.ico` |

The rights values are deliberately generic ("© Rights Holder… demonstration rights metadata for agencies"). The site demonstrates the fields; it doesn't claim to own the brand imagery.

## One image, three channels

The same pixels go out as a social ad, an email hero and a page image. Each channel reads a different layer, so one description has to be placed three ways. Using the game11ty share image as the example:

| Channel | What the machine reads | What survives | Where the description goes |
| --- | --- | --- | --- |
| Social ads and link previews | `og:image`, `og:image:alt`, `twitter:image:alt` from the page | Platforms typically re-encode uploads, so embedded XMP is usually lost | `og:image:alt` on the page, plus the alt-text field in the ad tool |
| Email | The `<img alt>` in the email HTML | Many clients block images until the reader allows them, and show the alt text instead; clients don't read XMP | A complete `alt` that works as copy on its own |
| Page | `alt`, the section's heading, JSON-LD, and the file's XMP | All three layers | `images.json` → `postsync.py` |

A 1×1 tracking pixel in an ad or email is the opposite case: it carries no meaning, so give it `alt=""`. Screen readers then skip it, and parsers don't mistake it for content.

### Section IDs paired with H1s as an index

An `alt` is read in the context of the section around it. The section's `id` is the machine address (a deep link such as `/game11ty/#complete-your-setup`), and its heading is the human label. Together they index the page, and the alt text should add to that label, not repeat it.

| Section `id` | H1 + H2 | Image | Alt text |
| --- | --- | --- | --- |
| `#omenhero` | Omen x Valorant / An Official Partner of the Valorant Champions Tour | Valorant logo | Valorant Champions Paris logo |
| `#omen-35L-valorant` | No H1 / OMEN 35L Valorant Gaming Desktop Special Edition | Desktop | OMEN 35L Valorant Gaming Desktop Special Edition with two lit front fans |
| `#follow-the-action` | No H1 / Follow the Action. Fuel Your Game. | Emblem | Red Valorant Champions emblem |
| `#complete-your-setup` | Complete / Your Valorant Setup | 3 product photos | Bundles for FPS Games: HyperX headset, microphone, keyboard and mouse on a desk (and two more) |
| `#why-omen-valorant` | Why / Omen x Valorant | Partnership art | OMEN, HyperX and Riot Games partnership artwork for Valorant |

This shows two gaps in game11ty. The page has three H1s, and two of them ("Complete", "Why") only make sense when read with the H2 below them. Two sections have no H1 at all. A parser building an outline gets "Complete" and "Why" as top-level topics. A cleaner index is one H1 for the page and an H2 per section that reads on its own:

```html
<section id="complete-your-setup">
  <h2>Complete your Valorant setup</h2>
  <img src="/game11ty/assets/…omentrio2_0014.jpg"
       alt="Bundles for FPS Games: HyperX headset, microphone, keyboard and mouse on a desk">
</section>
```

The ad or email then links to `/game11ty/#complete-your-setup`. Someone clicking through lands on the section whose heading, alt text and file metadata all say the same thing.

## 3D mesh data: CLO wraps and game objects

A 3D garment is a stack of images on a mesh. The fabric "wrap" is a set of UV-mapped textures (base colour, normal, sampler maps) laid over mesh geometry. That makes it two kinds of data, and only the textures have the XMP habits described above. glTF, the standard format for web and game 3D, has its own metadata slots, and they're usually left empty or filled in wrongly.

The CLO jean jacket and avatar on the board, as exported through Adobe Substance 3D Stager:

| File | Size | Mesh data | Textures | What its metadata says |
| --- | --- | --- | --- | --- |
| `jeanjacket.glb` | 8.2 MB | 152 meshes, 98,560 vertices, 6.1 MB | 19 embedded, 1.7 MB; 7 carry XMP | `asset.copyright`: "2025 (c) Adobe Inc." |
| `maramodel.glb` (avatar) | 2.1 MB | 12 meshes, 24,303 vertices | 7 embedded | `asset.copyright`: "2025 (c) Adobe Inc."; skeleton joints as plain nodes, no skin |
| `jeanjacket.gltf` + `.bin` + 21 loose images | 6.7 MB | same jacket, split into separate files | 8 of 21 carry XMP | same Adobe copyright |

Three things stand out:

- **The exporter claimed the copyright.** Stager wrote Adobe's own copyright line into `asset.copyright` on all three models. A crawler or marketplace reading that field would credit Adobe, not the designer. Overwrite it on export.
- **Names carry the lineage, not the metadata.** Node and material names record where each part came from: `JEANALL2%2Eroblox_n3d` (a Roblox-sourced scene), `Denim_Lightweight_FRONT_4584` (a CLO fabric), and `Mara:` and `Feifei_hair` (CLO avatar parts). That's useful tracking data, but it's informal and gets lost on rename.
- **No game-object IDs.** None of the 189 nodes has `extras` or an extension. A game engine or tracking system has nothing stable to hang analytics, SKUs or ownership on.

### Where 3D metadata goes in glTF

| Slot | Scope | Use it for |
| --- | --- | --- |
| `asset.copyright`, `asset.generator` | Whole file | Rights holder and the tool that made it |
| `KHR_xmp_json_ld` | Whole file, or one scene, node, mesh, material or image | Full XMP (`dc:`, `xmpRights:`, IPTC) as JSON-LD; object-level packets override the file-level one |
| `extras` | Any object | Your own tracking fields: game-object ID, SKU, garment piece |
| Texture XMP | Each embedded JPG or PNG | Alt text and rights for the wrap itself |

`KHR_xmp_json_ld` is a ratified Khronos extension ([spec](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_xmp_json_ld/README.md)). It lets the same rights fields used on game11ty's images travel inside the 3D file, down to a single garment piece. Here is the jacket with a file-level packet and one tracked game object:

```json
{
  "asset": { "version": "2.0", "copyright": "© Rights Holder", "generator": "CLO → Substance 3D Stager" },
  "extensionsUsed": ["KHR_xmp_json_ld"],
  "extensions": { "KHR_xmp_json_ld": { "packets": [{
    "@context": { "dc": "http://purl.org/dc/elements/1.1/",
                  "xmpRights": "http://ns.adobe.com/xap/1.0/rights/" },
    "@id": "",
    "dc:title": "Lightweight denim jacket",
    "dc:description": "Light-wash denim jacket on a CLO avatar, 152 garment pieces",
    "xmpRights:WebStatement": "https://example.com/rights/"
  }]}},
  "nodes": [{
    "name": "Cloth_mesh_n3d",
    "mesh": 0,
    "extras": { "gameObjectId": "jacket-front-left", "sku": "DJ-4584", "fabric": "Denim_Lightweight_FRONT_4584" },
    "extensions": { "KHR_xmp_json_ld": { "packet": 0 } }
  }]
}
```

The IDs and SKU are placeholders. Reading it back takes a few lines of Python, because a `.glb` keeps its JSON in the first chunk after a 20-byte header:

```python
import json, struct

data = open("jeanjacket.glb", "rb").read()
length = struct.unpack("<I", data[12:16])[0]       # JSON chunk length
gltf = json.loads(data[20:20 + length])

print(gltf["asset"].get("copyright"))              # who the file says owns it
for node in gltf["nodes"]:
    if "extras" in node:                             # tracked game objects
        print(node["name"], node["extras"].get("gameObjectId"))
```

Run against the real jacket today, the first line prints "2025 (c) Adobe Inc." and the loop prints nothing. That's the gap a 3D pipeline needs to close: the rights field is wrong and the game objects are untracked.

### Tool references: from Illustrator art to a 3D model

Artwork often starts as a vector in Illustrator, gets wrapped onto a model in Substance or Cinema 4D, and ends up in an After Effects render or a web viewer. Each hand-off is a chance to keep or lose the description and rights.

| Tool | What it makes | Metadata it keeps or writes | Where it's lost |
| --- | --- | --- | --- |
| **Illustrator** (3D and Materials panel) | Extruded and revolved 3D objects with Substance materials; exports glTF, USDA, USDZ and OBJ since version 27.0 ([Adobe](https://helpx.adobe.com/illustrator/desktop/special-effects-styles/create-3d-graphics/export-3d-vector-artwork.html)) | The `.ai` file's own XMP | OBJ export keeps only the object's colour, not its Substance materials |
| **Substance 3D** (Painter, Stager) | Texture sets (base colour, normal, roughness) and staged scenes exported as glTF/GLB ([Stager formats](https://helpx.adobe.com/substance-3d-stager/getting-started/import-export-formats.html)) | XMP in some exported textures; `asset.generator` | Stager wrote "2025 (c) Adobe Inc." into `asset.copyright` on the jacket and avatar |
| **Cinema 4D** | Modelling, UV unwrapping, animation; glTF 2.0 export with an optional Draco setting in recent versions ([guide](https://svilenkovic.com/3d/how-to-export-cinema4d-to-glb)) | Object and material names | Anything not mapped to a glTF field |
| **Cinema 4D Lite** (ships with After Effects) | A limited Cinema 4D for building 3D scenes that render inside After Effects through the Cineware plug-in ([Adobe](https://helpx.adobe.com/after-effects/using/c4d.html), [Maxon](https://help.maxon.net/cw/en-us/Content/html/CINEWARE_ADOBE_AFTER_EFFECTS_3D_FILE.html)) | Lives as a `.c4d` layer in the AE project | The 3D data stays in the AE project; renders carry only AE's XMP |
| **After Effects** | Video and image-sequence renders | With *Include Source XMP Metadata* on, writes markers, comments, project XMP and every source file's XMP into the render; off, only a unique ID ([Adobe](https://helpx.adobe.com/after-effects/using/xmp-metadata.html)) | Off by default in many output modules: check it |

The weak points are the exporters, not the tools. Set the copyright and description at the last export, check `asset.copyright` in every GLB, and turn on *Include Source XMP Metadata* in After Effects when a render has to carry rights.

### Video poster images

A video's poster frame is an ordinary JPG or PNG, so it carries XMP rights like any other image. It's also the part of a video that machines see first. A `<video>` element has no `alt`, crawlers index the thumbnail rather than decoding the video, and social previews show the poster. That makes the poster the video's rights label on the web.

```html
<video controls poster="/media/omen-teaser-poster.jpg"
       aria-label="OMEN x Valorant teaser: the OMEN 35L desktop on stage in Paris">
  <source src="/media/omen-teaser.mp4" type="video/mp4">
</video>
<script type="application/ld+json">
{ "@context": "https://schema.org", "@type": "VideoObject",
  "name": "OMEN x Valorant teaser",
  "description": "The OMEN 35L desktop on stage in Paris",
  "thumbnailUrl": "https://example.com/media/omen-teaser-poster.jpg",
  "uploadDate": "2026-10-03",
  "license": "https://example.com/rights/" }
</script>
```

The file names and dates are placeholders. Write the same description and rights into three places: the poster's XMP, the `VideoObject` JSON-LD (`thumbnailUrl` points at the poster), and the video file itself. For that last one, turn on *Include Source XMP Metadata* when rendering from After Effects. If the video is re-encoded or stripped, the poster still carries the rights.

### Video optimization in Adobe Media Encoder

Media Encoder is where a video's size and its metadata are decided together. The *Metadata* button in Export Settings offers two ways to keep XMP: *Embed in Output File* or *Create Sidecar File*, a separate `.xmp` next to the video ([Adobe](https://helpx.adobe.com/media-encoder/using/export-settings-reference.html)). Users on Adobe's forum report that embedding is greyed out for H.264 MP4 and available for QuickTime ([Adobe community](https://community.adobe.com/questions-729/embed-xmp-metadata-in-output-file-options-are-disabled-for-mp4-1341890)). So the most common web format often ships with no rights inside it.

| Setting | Web recommendation | Why |
| --- | --- | --- |
| Format | H.264 (MP4) for reach; H.265 or AV1 where supported | Smaller files at the same quality |
| Bitrate encoding | VBR, 2 pass | About 10% better quality for the same size, at roughly twice the encode time ([guide](https://annenbergdl.org/compress-video-for-the-web-with-media-encoder/)) |
| Maximum bitrate | About 2× the target | Leaves room for fast motion without raising the average |
| Target bitrate | About 16 Mbps for streaming uploads; lower for embedded web video | Platforms re-encode anyway; 32–40 Mbps is master quality ([guide](https://annenbergdl.org/compress-video-for-the-web-with-media-encoder/)) |
| Metadata | *Create Sidecar File* for MP4; *Embed* for QuickTime masters | Keeps the rights whether or not the container can hold XMP |
| Poster | Export a still frame as JPG and give it rights XMP | The frame crawlers and social previews index |

For game footage like the Valorant streams on the board, fast motion is what eats bitrate. Keep 2-pass VBR, and put the rights in the sidecar, the poster and the `VideoObject` JSON-LD. Don't rely on the MP4 alone.

### Draco compression

[Draco](https://github.com/google/draco) is Google's open-source codec for compressing mesh geometry: vertex positions, normals, UVs and triangles. It isn't a media type of its own. In glTF it's carried by the `KHR_draco_mesh_compression` extension ([Khronos](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_draco_mesh_compression/README.md)), and the file is still served as `model/gltf-binary` (`.glb`) or `model/gltf+json` (`.gltf`).

I ran the jean jacket through Draco with `gltf-transform` to see what it costs and what it keeps:

|  | Original | Draco |
| --- | --- | --- |
| File size | 8.19 MB | 2.86 MB (65% smaller) |
| `asset.copyright` | 2025 (c) Adobe Inc. | Kept |
| `asset.generator` | Adobe Substance 3D Stager | Replaced by glTF-Transform v4.5.1 |
| Node names (189) | `JEANALL2%2Eroblox_n3d` … | Kept |
| Textures with XMP | 7 of 19 | 7 of 19 (textures aren't touched) |
| Viewer needs | Any glTF viewer | A Draco decoder (`extensionsRequired`) |

Draco only compresses geometry, so the mesh data shrinks and the textures and their XMP pass through untouched. It does rewrite `asset.generator`, and the one tool-specific extension in the jacket (`EXT_materials_specular_edge_color`) triggered a warning. Run your rights and tracking fields through the compressor and check them afterwards, as you would for a WebP conversion.

**Two layers, two owners.** A 3D file splits the same way an image does. The geometry underlayer is open and Google-optimised: Draco compresses it and any glTF viewer with a decoder can read it. The shading layer is Adobe-bound. Substance materials are procedural inside Adobe's tools, and leave them only as baked textures plus standard PBR settings. In the jacket, the Khronos `KHR_materials_specular` setting survived Draco on 12 of 13 materials. Stager's own `EXT_materials_specular_edge_color` declaration was dropped, though no material used it. Rights for the geometry belong in glTF fields. Rights for the look belong in the texture XMP and the material's `KHR_xmp_json_ld` packet, because that's the part that stays tied to Adobe's material model.

## Checklist for agencies and media teams

- <input type="checkbox" disabled> Keep one description per image in a single source file, and generate the `alt`, XMP and JSON-LD from it
- <input type="checkbox" disabled> Write alt text that adds to the section's heading instead of repeating it
- <input type="checkbox" disabled> Give the page one H1 and each section an `id` plus a heading that reads on its own
- <input type="checkbox" disabled> Embed Copyright Notice, Creator, Credit Line, Web Statement of Rights, Licensor URL and a Data Mining value
- <input type="checkbox" disabled> Point the Web Statement of Rights and the JSON-LD `license` at the same live rights page
- <input type="checkbox" disabled> Set `og:image:alt` for every share image, and fill the alt-text field in ad tools
- <input type="checkbox" disabled> Write email alt text that works as copy when images are blocked; give tracking pixels `alt=""`
- <input type="checkbox" disabled> Turn on metadata keeping in every encoder and optimiser (e.g. `cwebp -metadata xmp`)
- <input type="checkbox" disabled> Strip edit history and padding from web copies; keep the full packet in the DAM
- <input type="checkbox" disabled> Serve favicons as PNG and ICO from a 512 px source, with no third-party logos
- <input type="checkbox" disabled> Re-check the live site with a parser after every build or sync

### exiftool commands

```bash
# Read the description and rights fields
exiftool -AltTextAccessibility -Description -Rights -WebStatement -LicensorURL -DataMining photo.jpg

# Write a minimal rights set (JPG, PNG and WebP)
exiftool -overwrite_original \
  "-XMP-iptcCore:AltTextAccessibility=Player at an OMEN desktop with red-lit fans" \
  "-MWG:Description=Player at an OMEN desktop with red-lit fans" \
  "-MWG:Copyright=© Rights Holder" "-MWG:Creator=Rights Holder" \
  "-XMP-xmpRights:WebStatement=https://example.com/rights/" \
  "-XMP-plus:LicensorURL=https://example.com/rights/" photo.jpg

# Web copy: drop edit history, keep everything else
exiftool -overwrite_original -XMP-xmpMM:all= photo.jpg
```

## Sources

- [IPTC Photo Metadata Standard 2025.1](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html)
- [Google Search Central: image license metadata](https://developers.google.com/search/docs/appearance/structured-data/image-license-metadata)
- [Google Search Central: favicons in search results](https://developers.google.com/search/docs/appearance/favicon-in-search)
- [WebP container specification](https://developers.google.com/speed/webp/docs/riff_container)
- [Khronos KHR\_xmp\_json\_ld](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_xmp_json_ld/README.md)
- [Khronos KHR\_draco\_mesh\_compression](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_draco_mesh_compression/README.md) and [Google Draco](https://github.com/google/draco)
- [Adobe: XMP metadata in After Effects](https://helpx.adobe.com/after-effects/using/xmp-metadata.html)
- [Adobe: Cinema 4D and Cineware in After Effects](https://helpx.adobe.com/after-effects/using/c4d.html) and [Maxon: Cineware](https://help.maxon.net/cw/en-us/Content/html/CINEWARE_ADOBE_AFTER_EFFECTS_3D_FILE.html)
- [Adobe: export 3D vector artwork in Illustrator](https://helpx.adobe.com/illustrator/desktop/special-effects-styles/create-3d-graphics/export-3d-vector-artwork.html)
- [Adobe: Substance 3D Stager import and export formats](https://helpx.adobe.com/substance-3d-stager/getting-started/import-export-formats.html)
- [Adobe: Media Encoder export settings reference](https://helpx.adobe.com/media-encoder/using/export-settings-reference.html), [Adobe community: XMP embed disabled for MP4](https://community.adobe.com/questions-729/embed-xmp-metadata-in-output-file-options-are-disabled-for-mp4-1341890) and [Annenberg Digital Lounge: compress video for the web with Media Encoder](https://annenbergdl.org/compress-video-for-the-web-with-media-encoder/)
- [Wikipedia: OpenAI–HuggingFace incident](https://en.wikipedia.org/wiki/OpenAI%E2%80%93HuggingFace_incident)
- [How to export Cinema 4D to GLB](https://svilenkovic.com/3d/how-to-export-cinema4d-to-glb)
- Measurements and parser output: game11ty files, the [live site](https://persephonepunch.github.io/game11ty/) and the CLO jacket and avatar GLBs, 3 October 2026
