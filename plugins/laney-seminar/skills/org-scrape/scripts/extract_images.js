// extract_images.js — Comprehensive page image & brand extraction (org-scrape skill)
// Usage: agent-browser --session <name> eval "$(cat skills/org-scrape/scripts/extract_images.js)"
//
// Returns a JSON object with all extracted assets from the current page:
//   images, backgroundImages, peoplePhotos, facilityPhotos, logos, favicons, brandColors, pageSignals

JSON.stringify((() => {
  // --- Helpers ---

  // Parse a srcset string and return the URL with the largest width descriptor.
  // Falls back to the first entry if no width descriptors are present.
  function bestFromSrcset(srcset) {
    if (!srcset) return null;
    const entries = srcset.split(",").map(s => s.trim()).filter(Boolean);
    let best = null;
    let bestW = -1;
    for (const entry of entries) {
      const parts = entry.split(/\s+/);
      const url = parts[0];
      const descriptor = parts[1] || "";
      const wMatch = descriptor.match(/^(\d+(?:\.\d+)?)w$/i);
      const w = wMatch ? parseFloat(wMatch[1]) : 0;
      if (w > bestW) { bestW = w; best = url; }
    }
    return best || (entries[0] ? entries[0].split(/\s+/)[0] : null);
  }

  // Collect srcset candidates from a <picture> element's <source> children.
  function pictureSourceCandidates(img) {
    const picture = img.closest("picture");
    if (!picture) return [];
    return Array.from(picture.querySelectorAll("source"))
      .map(s => bestFromSrcset(s.srcset || s.getAttribute("srcset")))
      .filter(Boolean);
  }

  // Placeholder / unloaded src patterns used by lazy-load libraries.
  const LAZY_PATTERNS = ["data:", "blank", "lazy", "placeholder", "pixel", "1x1", "spacer"];
  function isPlaceholderSrc(src) {
    if (!src) return true;
    const lower = src.toLowerCase();
    return LAZY_PATTERNS.some(p => lower.includes(p));
  }

  // Resolve the best available URL for an <img>, accounting for srcset, <picture>,
  // and lazy-load data attributes. Returns { bestSrc, lazy }.
  function resolveImg(img) {
    const candidates = [];

    // Collect <picture><source> srcset candidates first (highest quality source).
    candidates.push(...pictureSourceCandidates(img));

    // Own srcset
    const ownSrcset = img.srcset || img.getAttribute("srcset");
    const fromSrcset = bestFromSrcset(ownSrcset);
    if (fromSrcset) candidates.push(fromSrcset);

    // Plain src
    if (img.src) candidates.push(img.src);

    // Determine if the current src is a placeholder / not yet loaded
    const srcIsPlaceholder = isPlaceholderSrc(img.src) || img.naturalWidth === 0;
    let lazy = false;

    if (srcIsPlaceholder) {
      // Try data-* lazy-load attributes as fallback candidates
      const lazyAttrs = ["data-src", "data-original", "data-lazy", "data-srcset"];
      for (const attr of lazyAttrs) {
        const val = img.getAttribute(attr);
        if (val) {
          const resolved = attr.includes("srcset") ? bestFromSrcset(val) : val;
          if (resolved) candidates.push(resolved);
        }
      }
      lazy = true;
    }

    // Pick the first non-placeholder candidate; fall back to img.src
    const bestSrc = candidates.find(c => !isPlaceholderSrc(c)) || img.src || null;
    return { bestSrc, lazy };
  }

  // --- 1. All meaningful images (> 100x100, or lazy-load candidates) ---
  const images = Array.from(document.querySelectorAll("img"))
    .map(i => {
      const { bestSrc, lazy } = resolveImg(i);
      const entry = {
        src: i.src,
        bestSrc,
        alt: i.alt || "",
        w: i.naturalWidth,
        h: i.naturalHeight
      };
      if (lazy) entry.lazy = true;
      return entry;
    })
    .filter(i => (i.w > 100 && i.h > 100) || i.lazy);

  // --- 2. CSS background-image URLs ---
  // Builder sites (imweb, 카페24, Wix) render event banners / hero images as CSS
  // background-image on a DIV with HTML text overlaid — NOT as <img>. The old
  // `[style*=background-image]` selector caught only INLINE styles; banners set the
  // background via a CSS class, so we must read COMPUTED style on every element.
  // Size-filtered so we get banners (large) and skip 1px sprites / icons.
  const seenBg = new Set();
  const backgroundImages = [];
  Array.from(document.querySelectorAll("*")).forEach(el => {
    const w = el.offsetWidth, h = el.offsetHeight;
    if (w < 200 || h < 120) return;                 // banner-sized only
    const bg = getComputedStyle(el).backgroundImage;
    if (!bg || bg === "none" || !/url\(/.test(bg)) return;
    const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
    if (!m) return;
    const url = m[1];
    if (url.startsWith("data:") || seenBg.has(url)) return;
    seenBg.add(url);
    backgroundImages.push({
      src: url,
      bestSrc: url,
      w, h,
      // The overlaid HTML text is often the banner's real content (event name,
      // "59만원", period) — capture it so a price isn't lost when it's live text.
      context: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 200)
    });
  });

  // --- 3. People photos (doctors, lawyers, accountants, representatives, etc.) ---
  // Expanded from hospital-only to any org type.
  const peopleKeywords = ["원장", "의사", "doctor", "대표", "변호사", "세무사", "회계사", "프로필"];
  const peoplePhotos = Array.from(document.querySelectorAll("img"))
    .filter(i => {
      const ctx = (i.alt + " " + (i.closest("section,article,div")?.textContent || "")).toLowerCase();
      return peopleKeywords.some(k => ctx.includes(k))
             && (i.naturalWidth > 200 && i.naturalHeight > 200);
    })
    .map(i => {
      const { bestSrc, lazy } = resolveImg(i);
      const entry = {
        src: i.src,
        bestSrc,
        srcset: i.srcset || "",
        alt: i.alt,
        w: i.naturalWidth,
        h: i.naturalHeight,
        aspect: (i.naturalHeight / (i.naturalWidth || 1)).toFixed(2)
      };
      if (lazy) entry.lazy = true;
      return entry;
    });

  // --- 4. Facility / interior photos ---
  // Keywords extended with office / firm context ("사무실","사무소","접견실").
  const facilityKeywords = [
    "시설", "내부", "회복실", "상담실", "건물", "외관", "facility", "interior",
    "사무실", "사무소", "접견실"
  ];
  const facilityPhotos = Array.from(document.querySelectorAll("img"))
    .filter(i => {
      const ctx = (i.alt + " " + (i.closest("section,article,div")?.textContent || "")).toLowerCase();
      return facilityKeywords.some(k => ctx.includes(k))
             && i.naturalWidth > 400 && i.naturalHeight > 300;
    })
    .map(i => {
      const { bestSrc, lazy } = resolveImg(i);
      const entry = {
        src: i.src,
        bestSrc,
        alt: i.alt,
        w: i.naturalWidth,
        h: i.naturalHeight,
        ratio: (i.naturalWidth / (i.naturalHeight || 1)).toFixed(2)
      };
      if (lazy) entry.lazy = true;
      return entry;
    });

  // --- 5. Logo candidates ---
  const logos = Array.from(document.querySelectorAll("img"))
    .filter(i => {
      const alt = (i.alt || "").toLowerCase();
      const src = (i.src || "").toLowerCase();
      const isLogoAlt = alt.includes("로고") || alt.includes("logo");
      const isLogoSrc = src.includes("logo");
      const isSmallHeader = i.width < 300 && i.height < 100 && i.width > 10;
      const inHeader = !!i.closest("header, nav, [class*=header], [class*=nav], [class*=logo]");
      return isLogoAlt || isLogoSrc || (isSmallHeader && inHeader);
    })
    .map(i => {
      const { bestSrc } = resolveImg(i);
      return { src: i.src, bestSrc, alt: i.alt, w: i.width, h: i.height };
    });

  // --- 6. Favicons ---
  const favicons = Array.from(document.querySelectorAll("link[rel*=icon]"))
    .map(l => ({
      href: l.href,
      sizes: l.sizes?.value || null
    }));

  // --- 7. Brand colors ---
  const buttons = Array.from(document.querySelectorAll("button, .btn, a[class*=btn]"))
    .slice(0, 5)
    .map(el => ({
      text: el.textContent.trim().slice(0, 20),
      bg: getComputedStyle(el).backgroundColor,
      color: getComputedStyle(el).color
    }));

  const ignoredBgs = [
    "rgba(0, 0, 0, 0)", "transparent",
    "rgb(255, 255, 255)", "rgb(247, 247, 247)",
    "rgb(249, 249, 249)", "rgb(248, 248, 248)"
  ];

  const accents = Array.from(new Set(
    Array.from(document.querySelectorAll("div,section"))
      .map(el => getComputedStyle(el).backgroundColor)
      .filter(c => !ignoredBgs.includes(c))
  )).slice(0, 8);

  const footerEl = document.querySelector("footer");
  const footerBg = footerEl ? getComputedStyle(footerEl).backgroundColor : null;

  const brandColors = { buttons, accents, footerBg };

  // --- 8. Page signals ---
  // Helps downstream code decide how image-heavy vs text-heavy the page is.
  const allImgs = Array.from(document.querySelectorAll("img"));
  const textLength = (document.body?.innerText || "").trim().length;
  const imageCount = allImgs.length;
  const largeImgs = allImgs.filter(i => i.naturalWidth > 300 && i.naturalHeight > 300);
  const largeImageArea = largeImgs.reduce((sum, i) => sum + i.naturalWidth * i.naturalHeight, 0);
  // imageHeavy: page has very little text and multiple large images — likely image-only layout.
  const imageHeavy = textLength < 800 && largeImgs.length >= 2;

  const pageSignals = { textLength, imageCount, largeImageArea, imageHeavy };

  return {
    images,
    backgroundImages,
    peoplePhotos,
    facilityPhotos,
    logos,
    favicons,
    brandColors,
    pageSignals
  };
})());
