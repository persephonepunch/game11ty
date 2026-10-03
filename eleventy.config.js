import { HtmlBasePlugin } from "@11ty/eleventy"

export default function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/assets")
  // GitHub Pages serves this under /game11ty/; the plugin prefixes the
  // root-absolute /assets/... URLs that sync.py writes.
  eleventyConfig.addPlugin(HtmlBasePlugin)
  return {
    dir: { input: "src", includes: "_includes", output: "_site" },
    pathPrefix: process.env.PATH_PREFIX || "/",
  }
}
