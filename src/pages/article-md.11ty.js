import { readFileSync } from "node:fs"

// The article's own source, served as plain Markdown for the "Markdown" download,
// so the download can never drift from the page.
export const data = { permalink: "/docs/alt-xmp-favicons.md", eleventyExcludeFromCollections: true }

// The pipeline diagram as Mermaid, so it draws in GitHub and other Markdown
// viewers even when the PNG can't be fetched.
const PIPELINE = `\`\`\`mermaid
flowchart LR
  webflow["Webflow site<br/>design and publish"] --> sync["sync.py<br/>crawls, downloads assets,<br/>rewrites templates"]
  sync --> post["postsync.py<br/>alt text, XMP, JSON-LD,<br/>favicon.ico, PNG renames"]
  json["images.json<br/>one description per image"] -- feeds all three layers --> post
  post --> build["Eleventy build<br/>static HTML under /game11ty/"]
  build --> pages["GitHub Pages<br/>deployed on every push"]
\`\`\``


const LADDERS = `\`\`\`mermaid
flowchart TB
  subgraph publish["At publish"]
    p1{"1. Type matches its name?"} -- no --> b1[Block]
    p1 -- yes --> p2{"2. Well-formed for type?"}
    p2 -- no --> b2[Block]
    p2 -- yes --> p3{"3. Rights data agree?"}
    p3 -- no --> b3[Block]
    p3 -- yes --> p4{"4. Rule, list or key edit?"}
    p4 -- yes --> hr[Human review]
    p4 -- no --> p5["5. Publish, hash recorded"]
  end
  subgraph unfurl["At unfurl"]
    u1{"1. Verified preview bot?"} -- yes --> u2["2. Serve public view only"]
    u1 -- no --> u3{"3. Signed-in user on TLS?"}
    u3 -- yes --> u4["4. Serve account's files"]
    u3 -- no --> ub[Block]
  end
\`\`\``


const LAYERS = `\`\`\`mermaid
flowchart LR
  subgraph publish["At publish"]
    author["Author or AI"] --> scan["Release scan<br/>isolated, no network<br/>(built today)"]
  end
  subgraph unfurl["At unfurl"]
    req["Requester<br/>bot, user, scraper"]
  end
  subgraph cf["Cloudflare edge"]
    tls["TLS<br/>sealed in transit"]
    allow["Allow list<br/>verified bots, IPs"]
  end
  subgraph xano["Xano"]
    enc["Field encryption<br/>AES, key in env var"]
    addons["Addons<br/>rights record joined"]
  end
  scan --> tls --> enc
  req -- link preview or visit --> allow --> addons
\`\`\``

export function render({ site }) {
  const src = readFileSync("src/pages/article.md", "utf8")
  const [, fm, body] = src.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  const field = (k) => fm.match(new RegExp(`^${k}: "(.*)"$`, "m"))[1]
  const title = field("title")
  const md = body
    .replaceAll('<input type="checkbox" disabled> ', "[ ] ")
    // site-relative links break once the file is downloaded: make them absolute
    .replace(/\]\(\/(?!\/)/g, `](${site.url}/`)
    .replace(/(!\[[^\]]*\]\([^)]*pipeline-diagram\.png\))/, `$1\n\n${PIPELINE}`)
    .replace(/(!\[[^\]]*\]\([^)]*decision-ladders\.png\))/, `$1\n\n${LADDERS}`)
    .replace(/(!\[[^\]]*\]\([^)]*publish-unfurl-layers\.png\))/, `$1\n\n${LAYERS}`)
  const lead = `![${field("ogImageAlt")}](${site.url}${field("heroImage")})\n\n**Summary.** ${field("summary")}\n\n`
  return `# ${title}\n\n${lead}${md}`
}
