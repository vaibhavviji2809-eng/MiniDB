# Cost-Based Optimizer

The planner now compares candidate physical plans using estimated scan and join costs.

It considers:

- table scan cost
- index scan cost
- nested loop join cost
- hash join cost
- merge join cost
- index join cost

