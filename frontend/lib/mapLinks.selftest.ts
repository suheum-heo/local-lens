/**
 * Lightweight sanity checks for map link helpers.
 * Run: npx --yes tsx lib/mapLinks.selftest.ts
 */
import assert from "node:assert/strict";
import { googleMapUrl, kakaoMapUrl } from "./mapLinks";
import type { Restaurant } from "./types";

const base = {
  restaurant_id: "r1",
  name: "크레이지카츠",
  address: "서울 마포구 합정동 1",
  road_address: "서울 마포구 양화로 10",
  latitude: 37.55,
  longitude: 126.91,
  category: "음식점",
  kakao: {
    kakao_place_id: "83301316",
    name: "크레이지카츠",
    rating: 4.0,
    review_count: 100,
    place_url: "https://place.map.kakao.com/83301316",
  },
  google: {
    google_place_id: "ChIJ_test",
    name: "Crazy Katsu",
    rating: 4.2,
    user_rating_count: 80,
  },
  match: {
    confidence: 0.9,
    confidence_level: "high",
    matched: true,
    reason: null,
  },
  scores: {
    local: {
      availability: "available",
      rating: 4.0,
      review_count: 100,
      score: 80,
      explanation: null,
    },
    global: {
      availability: "available",
      rating: 4.2,
      review_count: 80,
      score: 78,
      explanation: null,
    },
    consensus: {
      availability: "available",
      rating: null,
      review_count: null,
      score: 79,
      explanation: null,
    },
  },
  label: "consensus_pick",
  rating_coverage: "both",
} as Restaurant;

assert.equal(kakaoMapUrl(base), "https://place.map.kakao.com/83301316");
assert.equal(
  googleMapUrl(base),
  "https://www.google.com/maps/place/?q=place_id:ChIJ_test",
);

const unmatched = {
  ...base,
  google: null,
  match: { ...base.match, matched: false, confidence: 0 },
} as Restaurant;
assert.match(
  googleMapUrl(unmatched),
  /maps\/search\/\?api=1&query=/,
);

const noPlaceUrl = {
  ...base,
  kakao: { ...base.kakao, place_url: null },
} as Restaurant;
assert.equal(kakaoMapUrl(noPlaceUrl), "https://place.map.kakao.com/83301316");

console.log("mapLinks.selftest: ok");
