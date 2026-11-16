/** The Natural Earth countries at 1:110m (`world-atlas`), a TopoJSON
 *  topology whose `countries` object names each country in `properties`.
 *  Declared here because the app does not resolve JSON modules for types;
 *  Vite bundles the file into the map's lazy chunk (round 11). */
declare module "world-atlas/countries-110m.json" {
  const topology: Parameters<typeof import("topojson-client").feature>[0];
  export default topology;
}
