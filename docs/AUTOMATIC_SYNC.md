# Automatic submodule synchronization

A successful `style` workflow for the current `main` commit triggers `Notify fleet
consumers`. It sends the authenticated `fleet-submodule-update` repository dispatch
event to enrolled consumers. Each consumer verifies the commit, advances its
fleet-style gitlink on its default branch, and pushes through its commit gates.
That push also runs the consumer's existing CI.

Follow the shared [configuration guide](https://github.com/DaizeDong/fleet-guards/blob/main/docs/AUTOMATIC_SYNC.md).
It covers the complete setup, token permissions, verification, and recovery.

The required configuration is:

- In each consumer, install fleet-guards and its fail-closed hook shims, copy the
  [consumer workflow](https://github.com/DaizeDong/fleet-guards/blob/main/templates/fleet-sync.yml)
  to `.github/workflows/fleet-sync.yml`, and set the `FLEET_SYNC_TOKEN` Actions secret.
  One workflow handles both kits. `.gitmodules` must use the public kit URL and
  track `main`, or omit `branch` to use `main`.
- In fleet-style, set `FLEET_SYNC_TARGETS` to a nonempty JSON array of subscriptions
  and `FLEET_SYNC_CREDENTIALS` to the corresponding credential mapping. A synthetic
  subscription is `{"repository":"example/consumer","credential":"primary"}`.
  Keep the real inventory in a private administration repository and tokens in a
  credential store. Neither belongs in this public repository.
- Verify `Notify fleet consumers`, then the consumer's `Sync fleet submodules`
  run, the resulting gitlink, and CI on the new consumer commit. A successful
  notification alone does not prove the consumer updated.

This uses GitHub's dispatch API as the webhook receiver. An ordinary repository
push webhook pointed directly at `/dispatches` cannot supply the authentication
or payload that the API requires, so no such repository hook is needed.

Consumers serialize updates and reconcile daily. Repeated updates make no extra
commit; stale notifications cannot move a pin backwards. API failures fail the
dispatcher visibly. Upstream checks must pass before a version is distributed;
consumer CI failures remain visible and are not automatically rolled back.

For recovery, rerun the source notification workflow or the affected consumer's
sync workflow. To stop synchronization, disable the consumer workflow and remove
its subscriptions from the source secrets.
