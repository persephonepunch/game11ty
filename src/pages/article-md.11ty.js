import { readFileSync } from "node:fs"

// The article's own source, served as plain Markdown for the "Markdown" download,
// so the download can never drift from the page.
export const data = { permalink: "/docs/alt-xmp-favicons.md", eleventyExcludeFromCollections: true }

export function render() {
  const src = readFileSync("src/pages/article.md", "utf8")
  const [, fm, body] = src.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  const title = fm.match(/^title: "(.*)"$/m)[1]
  return `# ${title}\n\n${body.replaceAll('<input type="checkbox" disabled> ', "[ ] ")}`
}
