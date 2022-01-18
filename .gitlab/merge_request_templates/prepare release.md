<!-- Use this template for MRs that prepare for a utopya release. -->

<!-- 1 - Set as MR title: Prepare release of vX.Y.Z -->

<!-- 2 - Fill in the MR description and the checklist below. -->

This MR prepares the vX.Y.Z release of utopya.


### Can this MR be accepted?
- [ ] Set version number in [`utopya/__init__.py`](utopya/__init__.py)
   - Removed the pre-release specifier.
   - Version is now: `X.Y.Z`
- [ ] Prepared [changelog](CHANGELOG.md) for release
   - Removed "WIP" in section heading
   - If necessary, re-ordered and cleaned-up the corresponding section
- [ ] Pipeline passes without warnings
   - If the `test` stage creates warnings for the `*_min` jobs, inspect the output log and, if necessary, adjust the lower bounds of the dependencies in [`setup.py`](setup.py).
- [ ] Approved by @  <!-- only necessary if there are substantial changes -->

<!-- 3 - If you are not allowed to merge, assign a maintainer now. -->

<!-- 4 - Adjust the following quick commands: -->
/label ~release
/milestone %"Version X.Y"
/assign @
