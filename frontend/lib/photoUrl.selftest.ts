/**
 * Run: npx --yes tsx lib/photoUrl.selftest.ts
 */
import assert from "node:assert/strict";
import { photoSrcLooksSafe, restaurantPhotoSrc } from "./photoUrl";

assert.equal(restaurantPhotoSrc(null), null);
assert.equal(restaurantPhotoSrc(undefined), null);

const proxy = restaurantPhotoSrc(
  "/api/restaurants/photo?photo_name=places%2FChIJ%2Fphotos%2Fmock_rep_1",
);
assert.ok(proxy);
assert.ok(proxy.includes("/api/restaurants/photo?photo_name="));
assert.ok(!proxy.includes("key="));
assert.ok(photoSrcLooksSafe(proxy));

assert.equal(
  restaurantPhotoSrc("https://places.googleapis.com/v1/x/media?key=secret"),
  null,
);
assert.equal(photoSrcLooksSafe("https://evil?key=AIza"), false);

console.log("photoUrl.selftest: ok");
