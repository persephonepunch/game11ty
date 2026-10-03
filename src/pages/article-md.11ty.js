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

export function render({ site }) {
  const src = readFileSync("src/pages/article.md", "utf8")
  const [, fm, body] = src.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  const title = fm.match(/^title: "(.*)"$/m)[1]
  const md = body
    .replaceAll('<input type="checkbox" disabled> ', "[ ] ")
    // site-relative links break once the file is downloaded: make them absolute
    .replace(/\]\(\/(?!\/)/g, `](${site.url}/`)
    .replace(/(!\[[^\]]*\]\([^)]*pipeline-diagram\.png\))/, `$1\n\n${PIPELINE}`)
  return `# ${title}\n\n${md}`
}
