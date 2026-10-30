# Origins and influences

## Name and starting point

Argus takes its name from Argus Panoptes, the hundred-eyed figure in Greek mythology. The connection is distributed observation: several robots and cameras contribute different views of the same environment.

[DimOS](https://github.com/dimensionalOS/dimos) supplied the project's original scene and camera conventions. MuJoCo supplies the simulation boundary, and Open3D supplies point-cloud processing tools.

## Technical influences

- **[Frontier exploration](https://ieeexplore.ieee.org/document/613851):** Direct motion toward boundaries between observed and unknown space.
- **[Voronoi partitioning](https://ieeexplore.ieee.org/document/1307178):** Bias robots toward different regions to reduce redundant exploration.
- **[Pure pursuit](https://www.ri.cmu.edu/pub_files/pub3/coulter_r_craig_1992_1/coulter_r_craig_1992_1.pdf):** Follow paths through a lookahead target.
- **[Raibert-style legged control](https://mitpress.mit.edu/9780262181174/):** Use an analytical gait as the Go2 locomotion baseline.
- **[Okabe-Ito colors](https://jfly.uni-koeln.de/color/):** Distinguish robots with an accessible categorical palette.

These are established ideas assembled into an experimental system. Their presence does not imply a new algorithm or a demonstrated performance advantage.

## Research influences

The scientific-method framing motivates controlled variables, explicit assumptions, and comparisons against baselines. The preference for small interfaces and simple implementations supports experiments that can be changed and inspected. Goodhart's law motivates checking whether a metric still represents the behavior being studied.

The practical consequence is a workbench organized around observable behavior and reproducible evidence. See [research methodology](research-method.md) and [systems design rationale](systems-design.md).
