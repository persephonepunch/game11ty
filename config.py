# Same job as design-sync/config.js - change `site` and re-run.
#
#     python3 sync.py            # uses this file
#     python3 sync.py --site ... # one-off override, doesn't edit the file

config = {
    # The published Webflow site to sync from.
    "site": "https://omen-valorant.webflow.io/",

    # Where the 11ty tree gets written.
    "out": ".",

    # Extra pages to seed the crawl with - anything not reachable by following
    # links from the homepage and not in sitemap.xml (design-sync's islandLinks).
    "pages": [],

    # Stop after this many pages, so a big site doesn't run away.
    "staticPageLimit": 200,

    # Delete the .w-webflow-badge element.
    "removeBranding": True,

    # Add `defer` to footer scripts and wrap trailing inline scripts in
    # DOMContentLoaded so they still run after the deferred ones.
    "optimizeJsLoading": True,

    # Move trailing scripts into footer.njk even when Webflow only emitted them
    # on some pages. Needed here: the .fs-menu-toggle handler was on 6 of 10
    # pages, so the mobile menu was dead on the other 4.
    "hoistPartialScripts": True,

    # Components from the repo (design-sync's replace() hook). A Webflow element
    # is swapped for src/_includes/components/<name>.njk when it has
    #   data-component="<name>"          (Element settings -> Custom attributes),
    #   a class listed in byClass        (a class the designer already uses), or
    #   the class "<classPrefix><name>"  (component-video -> video.njk).
    # Its data-* attributes arrive as props (data-market -> props.market), its
    # other classes as props.classes, its visible text as props.text. A name with
    # no .njk file is reported and left as Webflow drew it.
    # classPrefix: "" turns the convention off.
    "components": {
        "byClass": {},              # e.g. {"yt-lead": "video"}
        "classPrefix": "component-",
    },
}

# --- keys from design-sync/config.js that no longer apply -------------------
#
# clientRouting   next/link. 11ty emits plain <a>; the browser routes.
# revalidate      Next ISR. Nothing is fetched at request time any more.
# optimizeImages  next/image re-derived responsive variants at build time.
#                 Webflow already ships -p-500/-p-800/... derivatives and the
#                 sync keeps them plus the srcset, so this is already handled.
#                 (No WebP/AVIF conversion - that would be an eleventy-img pass.)
# minifyJs        UglifyJS over the fetched webflow.js. Not implemented; use a
#                 build-step minifier if you want it.
#
# Setting any of these has no effect, and sync.py will tell you so.
