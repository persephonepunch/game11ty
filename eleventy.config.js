import { HtmlBasePlugin } from "@11ty/eleventy"

export default function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/assets")
  eleventyConfig.addPassthroughCopy("src/docs")
  // Files in docs/ are downloads, copied as-is, never rendered as pages.
  eleventyConfig.ignores.add("src/docs/**")
  eleventyConfig.addPassthroughCopy("src/favicon.ico")
  // GitHub Pages serves this under /game11ty/; the plugin prefixes the
  // root-absolute /assets/... URLs that sync.py writes.
  eleventyConfig.addPlugin(HtmlBasePlugin)

  // _data/images.json -> schema.org ImageObjects, so the alt text in the HTML,
  // the XMP inside each file and the JSON-LD all say the same thing.
  eleventyConfig.addFilter("imageObjects", (images, siteUrl, rights) =>
    images.map((img) => ({
      "@type": "ImageObject",
      contentUrl: siteUrl + img.src,
      name: img.title,
      description: img.alt,
      caption: img.alt,
      copyrightNotice: rights.notice,
      creator: { "@type": "Organization", name: rights.holder },
      creditText: "Respective rights holders (demo)",
      license: rights.url,
      acquireLicensePage: rights.url,
    })),
  )


  // Knowledge-base pages: give every h2/h3 an id, wrap each h2 in its own
  // <section id>, wrap tables for sideways scroll, and fill the sidebar TOC.
  eleventyConfig.addTransform("kb", (content, outputPath) => {
    if (!outputPath || !content.includes("<!--kb-toc-->")) return content
    const slug = (s) => s.replace(/<[^>]+>/g, "").toLowerCase().replace(/&[a-z]+;/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
    const toc = []
    let n = 0
    let html = content.replace(/<h([23])>(.*?)<\/h\1>/g, (_, level, text) => {
      const id = slug(text)
      if (level === "2" && text !== "Sources") text = `${++n}. ${text}`
      toc.push(`<a href="#${id}"${level === "3" ? ' class="sub"' : ""}>${text.replace(/<[^>]+>/g, "")}</a>`)
      return `<h${level} id="${id}">${text}</h${level}>`
    })
    const start = html.indexOf('<h2 id="'), end = html.lastIndexOf("</article>")
    if (start > -1) {
      const body = html.slice(start, end).split(/(?=<h2 id=")/).map((part) => {
        const id = part.match(/<h2 id="([^"]+)"/)[1]
        return `<section id="${id}-section" aria-labelledby="${id}">${part}</section>\n`
      }).join("")
      html = html.slice(0, start) + body + html.slice(end)
    }
    html = html.replace(/<table>/g, '<div class="table-wrap"><table>').replace(/<\/table>/g, "</table></div>")
    return html.replace("<!--kb-toc-->", toc.join(""))
  })

  return {
    dir: { input: "src", includes: "_includes", output: "_site" },
    pathPrefix: process.env.PATH_PREFIX || "/",
  }
}
