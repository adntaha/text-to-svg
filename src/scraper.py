import asyncio
import aiohttp
from time import time
from bs4 import BeautifulSoup, Tag


STARTING_URL = "https://www.google.com/search?q=svg"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0"
}
SITE_DEPTH = 10

all_svgs: list[list[str]] = []
svg_count = 0


def clear_useless_classes(svg: Tag):
    svg.attrs.pop("class", None)
    svg.attrs.pop("focusable", None)
    for child in svg.children:
        if isinstance(child, Tag):
            clear_useless_classes(child)


async def scrape_svgs(response: aiohttp.ClientResponse):
    global all_svgs, svg_count

    soup = BeautifulSoup(await response.text(), "html.parser")
    svgs = soup.find_all("svg")

    for svg in svgs:
        clear_useless_classes(svg)

        if str(svg).replace("\n", "") not in map(
            lambda x: x[1].replace("\n", ""), all_svgs
        ):
            all_svgs.append([str(response.real_url), str(svg)])
            svg_count += 1
            print(
                f"{time()}: Found SVG on {str(response.real_url.origin()) + response.real_url.path} ({svg_count} total)"
            )


async def fetch_and_clean_urls(response: aiohttp.ClientResponse):
    soup = BeautifulSoup(await response.text(), "html.parser")

    anchors = soup.find_all("a")
    urls = []

    for anchor in anchors:
        if anchor.name.lower() == "use" and anchor.attrs.get(
            "xlink:href", ""
        ).startswith("/"):
            anchor.attrs["xlink:href"] = (
                str(response.real_url.origin()) + anchor.attrs["xlink:href"]
            )
        if anchor.attrs.get("href", "").startswith("//"):
            anchor.attrs["href"] = response.real_url.scheme + ":" + anchor.attrs["href"]
        elif anchor.attrs.get("href", "").startswith("/"):
            anchor.attrs["href"] = (
                str(response.real_url.origin()) + anchor.attrs["href"]
            )

        elif anchor.attrs.get("href", "").startswith("./"):
            anchor.attrs["href"] = str(response.real_url.origin()) + (
                anchor.attrs.get("href", "").replace("./", "/")
            )

        elif anchor.attrs.get("href", "").startswith("#") or (
            anchor.attrs.get("href", "").startswith("?")
        ):
            anchor.attrs["href"] = str(response.real_url)
        elif not anchor.attrs.get("href", "").startswith("http"):
            anchor.attrs["href"] = str(response.real_url.origin()) + (
                "/" + anchor.attrs.get("href", "")
            )

        urls.append(anchor.attrs.get("href", ""))

    return urls


async def perform_crawl(
    session: aiohttp.ClientSession, response: aiohttp.ClientResponse
):
    global SITE_DEPTH, HEADERS

    if SITE_DEPTH <= 0:
        return
    else:
        SITE_DEPTH -= 1

    urls = await fetch_and_clean_urls(response)

    for url in urls:
        async with session.get(url) as newResponse:
            await scrape_svgs(newResponse)
            await perform_crawl(session, newResponse)


async def main():
    global STARTING_URL, HEADERS, all_svgs
    async with aiohttp.ClientSession() as session:
        session._prepare_headers(HEADERS)
        async with session.get(STARTING_URL) as response:
            await perform_crawl(session, response)
            print("Done!")
            with open("all_svgs.html", "w") as f:
                htmldoc = [f"<!-- {svg[0]} -->\n{svg[1]}" for svg in all_svgs]
                f.write("\n\n".join(htmldoc))


if __name__ == "__main__":
    asyncio.run(main())
