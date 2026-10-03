import { HtmlBasePlugin } from "@11ty/eleventy"

export default function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/assets")
  eleventyConfig.addPassthroughCopy("src/docs")
  eleventyConfig.addPassthroughCopy("src/icons")
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
      description: img.alt,
      caption: img.alt,
      copyrightNotice: rights.notice,
      creator: { "@type": "Organization", name: rights.holder },
      creditText: "Respective rights holders (demo)",
      license: rights.url,
      acquireLicensePage: rights.url,
    })),
  )

  return {
    dir: { input: "src", includes: "_includes", output: "_site" },
    pathPrefix: process.env.PATH_PREFIX || "/",
  }
}
