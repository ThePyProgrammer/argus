# Scene source

Vendored unchanged from https://github.com/markusgrotz/mujoco-scene-editor/tree/a401997a9f5d02ab5073d5901fb37df4ff278a17/examples/prompt

Revision: `a401997a9f5d02ab5073d5901fb37df4ff278a17`. Copyright 2025 Markus Grotz; MIT license (see LICENSE.md).

Argus keeps these XML files unchanged. Its loader removes redundant `pos` on
`fromto` geoms (office) and promotes free-joint tools from the identity-transform
bench to the world (workbench) to fix upstream MJCF compilation errors.
Robot integration retains Argus physics options and namespaces environment names.

Unnamed geometry receives stable internal names for matching browser previews to physics.
