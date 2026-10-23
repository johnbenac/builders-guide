<!-- chunk: g5--3-step-by-step-3-2-walls-openings-door-and-windo | source: 05-worked-example.md | title: 3. Step by step: 3.2 Walls, openings, door and window (B-40 to B-44) | rules: - -->
### 3.2 Walls, openings, door and window (B-40 to B-44)

Each wall is an extruded rectangle. The door and the window each have an `IfcOpeningElement` that voids a wall
(`IfcRelVoidsElement`) and is filled by the door or window (`IfcRelFillsElement`). The doorway is 2.3 m high and nothing crosses it.
In the file:

```
#700198=IFCRELVOIDSELEMENT('1C_9SKyzTHcQf6qIs0XZ4T',$,$,$,#700125,#700197);
#700216=IFCDOOR('3Z2k6lcTnJFPCzw1CFlWEi',$,'Entrance door',$,$,#700213,#700215,$,2.3,1.2,.DOOR.,.SINGLE_SWING_LEFT.,$);
#700217=IFCRELFILLSELEMENT('29lMJRl7DVmRJwjxlT70xI',$,$,$,#700197,#700216);
```
