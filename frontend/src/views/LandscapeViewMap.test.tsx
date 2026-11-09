import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import PublisherMap, { atlasName, mapStep, matchKey, MAP_STEPS } from "./LandscapeViewMap";

function Location() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname + location.search}</p>;
}

function renderMap(countries: { country: string; count: number }[]) {
  return render(
    <MemoryRouter initialEntries={["/landscape"]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <PublisherMap
                countries={countries}
                caption="Where sources were published"
                hrefFor={(country) => `/all?country=${encodeURIComponent(country)}`}
              />
              <Location />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("atlasName", () => {
  it("places the server's country names on the atlas, abbreviations and all", () => {
    expect(atlasName("United Kingdom")).toBe("United Kingdom");
    expect(atlasName("United States")).toBe("United States of America");
    expect(atlasName("Czech Republic")).toBe("Czechia");
    expect(atlasName("Democratic Republic of the Congo")).toBe("Dem. Rep. Congo");
    expect(atlasName("Netherlands (the)")).toBe("Netherlands");
    expect(atlasName("Tanzania, United Republic of")).toBe("Tanzania");
    expect(atlasName("Côte d'Ivoire")).toBe("Côte d'Ivoire");
  });

  it("returns null for a region or a country too small for the map", () => {
    expect(atlasName("Global")).toBeNull();
    expect(atlasName("EU")).toBeNull();
    expect(atlasName("Singapore")).toBeNull();
  });

  it("matches without case, accents or a leading 'the'", () => {
    expect(matchKey("The Gambia")).toBe("gambia");
    expect(matchKey("CÔTE D'IVOIRE")).toBe("cote d'ivoire");
  });
});

describe("mapStep", () => {
  it("steps counts on a log scale, the largest the darkest", () => {
    expect(mapStep(1, 30)).toBe(0);
    expect(mapStep(30, 30)).toBe(MAP_STEPS.length - 1);
    expect(mapStep(5, 30)).toBeGreaterThan(mapStep(2, 30));
    expect(mapStep(4, 1)).toBe(MAP_STEPS.length - 1);
  });
});

describe("PublisherMap", () => {
  it("fills the countries with sources, lists what it cannot place, and opens a country on a press", () => {
    renderMap([
      { country: "United Kingdom", count: 30 },
      { country: "United States", count: 8 },
      { country: "Global", count: 2 },
      { country: "EU", count: 1 },
    ]);
    expect(screen.getByRole("img", { name: "Where sources were published" })).toBeInTheDocument();
    expect(screen.getByTestId("not-on-map")).toHaveTextContent("Not on the map: Global, EU");
    const uk = document.querySelector('[data-country="United Kingdom"]') as SVGPathElement;
    expect(uk.style.getPropertyValue("--fill")).toContain("100%");
    expect(document.querySelector('[data-country="United States"]')).toHaveAttribute("data-link");
    fireEvent.click(uk);
    expect(screen.getByTestId("location")).toHaveTextContent("/all?country=United%20Kingdom");
  });

  it("names a hovered country and its count in the tooltip", () => {
    renderMap([{ country: "United Kingdom", count: 23 }]);
    const uk = document.querySelector('[data-country="United Kingdom"]') as SVGPathElement;
    fireEvent.pointerMove(uk, { pointerType: "mouse", clientX: 10, clientY: 10 });
    expect(screen.getByRole("tooltip")).toHaveTextContent("United Kingdom · 23");
    expect(uk).toHaveAttribute("data-hover");
  });
});
