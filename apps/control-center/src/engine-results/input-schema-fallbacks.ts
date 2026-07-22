type Schema = Record<string, unknown>;

const number = (title: string, options: Record<string, unknown> = {}): Schema => ({ type: "number", title, ...options });
const array = (title: string, items: Schema, options: Record<string, unknown> = {}): Schema => ({ type: "array", title, items, ...options });
const object = (properties: Record<string, Schema>, required: string[], options: Record<string, unknown> = {}): Schema => ({ type: "object", properties, required, additionalProperties: false, ...options });

const vector3 = (title: string, value: [number, number, number] = [0, 0, 0]) => array(title, number("value"), { minItems: 3, maxItems: 3, default: value });

// The deployed Phase 2A registry predates detailed JSON Schema declarations and
// intentionally publishes a generic object schema. These local, versioned
// fallbacks mirror the public engine input validators. They are used only until
// an engine provides a more specific trusted schema of its own.
const builtinSchemas: Record<string, Schema> = {
  "math.sympy": object({
    operation: { type: "string", title: "Operation", enum: ["evaluate", "substitute", "simplify", "solve_linear"], default: "evaluate" },
    expression: { type: "string", title: "Expression", default: "2 + 2", maxLength: 2000 },
    equation: { type: "string", title: "Equation (for solve linear)", default: "x + 2 = 5", maxLength: 2000 },
    variable: { type: "string", title: "Variable", default: "x", maxLength: 80 },
  }, ["operation"]),
  "physics.simple_projectile": object({
    initial_position: vector3("Initial position (m)"),
    initial_velocity: vector3("Initial velocity (m/s)", [1, 5, 0]),
    gravity_m_s2: number("Gravity (m/s²)", { minimum: 0, default: 9.80665 }),
    duration_seconds: number("Duration (s)", { minimum: 0.001, maximum: 100, default: 1 }),
    time_step_seconds: number("Time step (s)", { minimum: 0.0001, maximum: 2, default: 0.05 }),
  }, ["duration_seconds"]),
  "physics.simple_collision": object({
    mass_a: number("Mass A (kg)", { minimum: 0.000001, default: 1 }),
    mass_b: number("Mass B (kg)", { minimum: 0.000001, default: 1 }),
    velocity_a: number("Velocity A (m/s)", { default: 2 }),
    velocity_b: number("Velocity B (m/s)", { default: 0 }),
  }, ["mass_a", "mass_b", "velocity_a", "velocity_b"]),
  "physics.n_body": object({
    bodies: array("Bodies (2–8)", object({ id: { type: "string", title: "ID", maxLength: 80 }, mass_kg: number("Mass (kg)", { minimum: 0.000000000001 }), position_m: vector3("Position (m)"), velocity_m_s: vector3("Velocity (m/s)") }, ["id", "mass_kg", "position_m", "velocity_m_s"]), { minItems: 2, maxItems: 8, default: [{ id: "a", mass_kg: 1000000000000, position_m: [-1, 0, 0], velocity_m_s: [0, 0.01, 0] }, { id: "b", mass_kg: 1000000000000, position_m: [1, 0, 0], velocity_m_s: [0, -0.01, 0] }] }),
    duration_seconds: number("Duration (s)", { minimum: 0.001, maximum: 100, default: 5 }),
    time_step_seconds: number("Time step (s)", { minimum: 0.0001, maximum: 2, default: 0.05 }),
    gravitational_constant: number("Gravitational constant", { minimum: 0.00000000000000000001, default: 0.000000000066743 }),
  }, ["bodies", "duration_seconds"]),
  "chemistry.reaction_kinetics": object({
    species: { type: "object", title: "Species concentrations", default: { A: 1, B: 0 }, additionalProperties: true },
    reactions: array("Reactions", object({ reactants: { type: "object", title: "Reactants", default: { A: 1 }, additionalProperties: true }, products: { type: "object", title: "Products", default: { B: 1 }, additionalProperties: true }, rate_constant: number("Rate constant", { minimum: 0, default: 0.2 }) }, ["reactants", "products", "rate_constant"]), { minItems: 1, maxItems: 32, default: [{ reactants: { A: 1 }, products: { B: 1 }, rate_constant: 0.2 }] }),
    duration_seconds: number("Duration (s)", { minimum: 0.001, maximum: 100, default: 5 }),
    time_step_seconds: number("Time step (s)", { minimum: 0.0001, maximum: 2, default: 0.05 }),
  }, ["species", "reactions", "duration_seconds"]),
  "biology.population_dynamics": object({
    model: { type: "string", title: "Model", enum: ["logistic", "lotka_volterra"], default: "logistic" },
    initial_population: number("Initial population", { minimum: 0, default: 20 }),
    growth_rate: number("Growth rate", { default: 0.5 }),
    carrying_capacity: number("Carrying capacity", { minimum: 0.000000000001, default: 100 }),
    prey_initial: number("Initial prey", { minimum: 0, default: 40 }),
    predator_initial: number("Initial predators", { minimum: 0, default: 9 }),
    prey_growth: number("Prey growth", { minimum: 0, default: 1.1 }),
    predation: number("Predation", { minimum: 0, default: 0.04 }),
    predator_efficiency: number("Predator efficiency", { minimum: 0, default: 0.01 }),
    predator_death: number("Predator death", { minimum: 0, default: 0.4 }),
    duration_seconds: number("Duration (s)", { minimum: 0.001, maximum: 100, default: 10 }),
    time_step_seconds: number("Time step (s)", { minimum: 0.0001, maximum: 2, default: 0.05 }),
  }, ["model", "duration_seconds"]),
  "engineering.dc_circuit": object({
    source_voltage_v: number("Source voltage (V)", { minimum: 0, maximum: 60, default: 5 }),
    resistance_top_ohm: number("Top resistance (Ω)", { minimum: 0.001, default: 1000 }),
    resistance_bottom_ohm: number("Bottom resistance (Ω)", { minimum: 0.001, default: 1000 }),
  }, ["resistance_top_ohm", "resistance_bottom_ohm"]),
};

function detailed(schema: unknown): schema is Schema {
  return Boolean(schema && typeof schema === "object" && !Array.isArray(schema) && Object.keys((schema as Schema).properties as object ?? {}).length > 0);
}

export function engineInputSchema(engineId: string, published: unknown): unknown {
  return detailed(published) ? published : builtinSchemas[engineId] ?? published;
}
