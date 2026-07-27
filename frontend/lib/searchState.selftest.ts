/**
 * Lightweight sanity checks for URL search-state helpers.
 * Run: npx --yes tsx lib/searchState.selftest.ts
 */
import assert from "node:assert/strict";
import {
  buildSearchParams,
  parseSearchParams,
} from "./searchState";

const params = buildSearchParams({
  city: "seoul",
  mode: "station",
  locationIds: ["st_hapjeong", "st_sangsu"],
  radiusM: 1500,
  query: "삼겹살",
  run: true,
});

assert.equal(params.get("city"), "seoul");
assert.equal(params.get("mode"), "station");
assert.equal(params.get("locs"), "st_hapjeong,st_sangsu");
assert.equal(params.get("radius"), "1500");
assert.equal(params.get("q"), "삼겹살");
assert.equal(params.get("run"), "1");

const parsed = parseSearchParams(params);
assert.equal(parsed.city, "seoul");
assert.equal(parsed.mode, "station");
assert.deepEqual(parsed.locationIds, ["st_hapjeong", "st_sangsu"]);
assert.equal(parsed.radiusM, 1500);
assert.equal(parsed.query, "삼겹살");
assert.equal(parsed.run, true);

const invalid = parseSearchParams(new URLSearchParams("radius=750&city=mars"));
assert.equal(invalid.radiusM, undefined);
assert.equal(invalid.city, undefined);

console.log("searchState.selftest: ok");
