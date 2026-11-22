// Built-in generic foods, values per 100 g (approximate; USDA FoodData Central and the Mexican
// equivalents system SMAE as references). Prepared dishes vary a lot by recipe: treat them as
// estimates. Format: [name, kcal, protein, carbs, fat, portion label, portion grams, category]

const RAW = [
  // Cereales, tortillas y tubérculos
  ['Tortilla de maíz', 218, 5.7, 44.6, 2.8, '1 pieza', 30, 'Cereales'],
  ['Tortilla de harina', 304, 8.1, 50, 7.9, '1 pieza', 40, 'Cereales'],
  ['Arroz blanco cocido', 130, 2.7, 28.2, 0.3, '1 taza', 158, 'Cereales'],
  ['Arroz integral cocido', 123, 2.7, 25.6, 1, '1 taza', 195, 'Cereales'],
  ['Arroz rojo (a la mexicana)', 150, 2.8, 26, 4, '1 taza', 180, 'Cereales'],
  ['Pan blanco de caja', 266, 7.6, 49, 3.3, '1 rebanada', 28, 'Cereales'],
  ['Pan integral de caja', 252, 12.5, 43, 3.5, '1 rebanada', 32, 'Cereales'],
  ['Bolillo', 270, 9, 53, 2.5, '1 pieza', 70, 'Cereales'],
  ['Pan dulce (concha)', 380, 7, 55, 15, '1 pieza', 75, 'Cereales'],
  ['Avena en hojuelas (cruda)', 389, 16.9, 66.3, 6.9, '1/2 taza', 40, 'Cereales'],
  ['Pasta cocida', 158, 5.8, 30.9, 0.9, '1 taza', 140, 'Cereales'],
  ['Papa cocida', 87, 1.9, 20.1, 0.1, '1 mediana', 150, 'Cereales'],
  ['Camote cocido', 90, 2, 20.7, 0.2, '1 mediano', 130, 'Cereales'],
  ['Elote cocido', 96, 3.4, 21, 1.5, '1 pieza', 100, 'Cereales'],
  ['Cereal de hojuelas de maíz', 357, 7.5, 84, 0.4, '1 taza', 28, 'Cereales'],
  ['Granola', 471, 10, 64, 20, '1/4 taza', 30, 'Cereales'],
  ['Tostada de maíz', 440, 6.5, 66, 17, '1 pieza', 12, 'Cereales'],
  ['Galletas María', 436, 7, 75, 12, '4 piezas', 24, 'Cereales'],
  ['Palomitas naturales', 387, 13, 78, 4.5, '3 tazas', 24, 'Cereales'],

  // Leguminosas
  ['Frijoles negros cocidos', 132, 8.9, 23.7, 0.5, '1/2 taza', 86, 'Leguminosas'],
  ['Frijoles refritos', 100, 5.5, 14.5, 2.5, '1/2 taza', 120, 'Leguminosas'],
  ['Lentejas cocidas', 116, 9, 20, 0.4, '1/2 taza', 100, 'Leguminosas'],
  ['Garbanzos cocidos', 164, 8.9, 27.4, 2.6, '1/2 taza', 82, 'Leguminosas'],

  // Carnes, pescados y huevo
  ['Pechuga de pollo cocida (sin piel)', 165, 31, 0, 3.6, '1 porción', 120, 'Proteínas'],
  ['Muslo de pollo cocido (sin piel)', 209, 26, 0, 10.9, '1 pieza', 100, 'Proteínas'],
  ['Huevo entero', 143, 12.6, 0.7, 9.5, '1 pieza', 50, 'Proteínas'],
  ['Clara de huevo', 52, 10.9, 0.7, 0.2, '1 clara', 33, 'Proteínas'],
  ['Carne molida de res 90/10 (cocida)', 217, 26, 0, 11.8, '1 porción', 100, 'Proteínas'],
  ['Bistec de res cocido', 200, 30, 0, 8, '1 porción', 120, 'Proteínas'],
  ['Lomo de cerdo cocido', 196, 27, 0, 9, '1 porción', 120, 'Proteínas'],
  ['Atún en agua (escurrido)', 116, 25.5, 0, 0.8, '1 lata', 100, 'Proteínas'],
  ['Salmón cocido', 206, 22, 0, 12.4, '1 filete', 120, 'Proteínas'],
  ['Tilapia cocida', 128, 26, 0, 2.7, '1 filete', 120, 'Proteínas'],
  ['Camarón cocido', 99, 24, 0.2, 0.3, '1 porción', 100, 'Proteínas'],
  ['Jamón de pavo', 110, 17, 3, 3.5, '1 rebanada', 20, 'Proteínas'],
  ['Salchicha de pavo', 180, 12, 4, 13, '1 pieza', 40, 'Proteínas'],
  ['Chorizo', 455, 24, 2, 38, '1 porción', 40, 'Proteínas'],
  ['Tocino cocido', 541, 37, 1.4, 42, '1 tira', 8, 'Proteínas'],
  ['Proteína en polvo (whey)', 380, 78, 8, 5, '1 scoop', 30, 'Proteínas'],
  ['Tofu firme', 144, 17.3, 2.8, 8.7, '1 porción', 100, 'Proteínas'],

  // Lácteos
  ['Leche entera', 61, 3.2, 4.8, 3.3, '1 vaso (240 ml)', 240, 'Lácteos'],
  ['Leche descremada', 34, 3.4, 5, 0.1, '1 vaso (240 ml)', 240, 'Lácteos'],
  ['Bebida de almendra sin azúcar', 15, 0.6, 0.3, 1.2, '1 vaso (240 ml)', 240, 'Lácteos'],
  ['Yogur natural', 61, 3.5, 4.7, 3.3, '1 vaso', 150, 'Lácteos'],
  ['Yogur griego natural', 97, 9, 3.9, 5, '1 envase', 170, 'Lácteos'],
  ['Yogur griego 0% grasa', 59, 10.2, 3.6, 0.4, '1 envase', 170, 'Lácteos'],
  ['Queso panela', 245, 18, 3, 18, '1 rebanada', 40, 'Lácteos'],
  ['Queso Oaxaca', 300, 22, 2, 23, '1 porción', 30, 'Lácteos'],
  ['Queso fresco', 299, 18, 3, 24, '1 porción', 30, 'Lácteos'],
  ['Queso cheddar', 403, 25, 1.3, 33, '1 rebanada', 20, 'Lácteos'],
  ['Queso cottage', 98, 11, 3.4, 4.3, '1/2 taza', 113, 'Lácteos'],
  ['Crema', 198, 2.4, 4.6, 19, '1 cucharada', 15, 'Lácteos'],
  ['Mantequilla', 717, 0.9, 0.1, 81, '1 cucharadita', 5, 'Lácteos'],

  // Frutas
  ['Plátano', 89, 1.1, 22.8, 0.3, '1 mediano', 118, 'Frutas'],
  ['Manzana', 52, 0.3, 13.8, 0.2, '1 mediana', 182, 'Frutas'],
  ['Naranja', 47, 0.9, 11.8, 0.1, '1 mediana', 131, 'Frutas'],
  ['Mango', 60, 0.8, 15, 0.4, '1 taza', 165, 'Frutas'],
  ['Papaya', 43, 0.5, 10.8, 0.3, '1 taza', 145, 'Frutas'],
  ['Sandía', 30, 0.6, 7.6, 0.2, '1 taza', 152, 'Frutas'],
  ['Melón', 34, 0.8, 8.2, 0.2, '1 taza', 160, 'Frutas'],
  ['Piña', 50, 0.5, 13.1, 0.1, '1 taza', 165, 'Frutas'],
  ['Fresas', 32, 0.7, 7.7, 0.3, '1 taza', 152, 'Frutas'],
  ['Uvas', 69, 0.7, 18.1, 0.2, '1 taza', 151, 'Frutas'],
  ['Pera', 57, 0.4, 15.2, 0.1, '1 mediana', 178, 'Frutas'],
  ['Guayaba', 68, 2.6, 14.3, 1, '1 pieza', 55, 'Frutas'],
  ['Kiwi', 61, 1.1, 14.7, 0.5, '1 pieza', 69, 'Frutas'],
  ['Arándanos', 57, 0.7, 14.5, 0.3, '1 taza', 148, 'Frutas'],
  ['Aguacate', 160, 2, 8.5, 14.7, '1/2 pieza', 70, 'Frutas'],
  ['Jugo de limón', 22, 0.4, 6.9, 0.2, '1 cucharada', 15, 'Frutas'],

  // Verduras
  ['Brócoli cocido', 35, 2.4, 7.2, 0.4, '1 taza', 156, 'Verduras'],
  ['Espinaca cruda', 23, 2.9, 3.6, 0.4, '1 taza', 30, 'Verduras'],
  ['Lechuga', 17, 1.2, 3.3, 0.3, '1 taza', 50, 'Verduras'],
  ['Jitomate', 18, 0.9, 3.9, 0.2, '1 pieza', 123, 'Verduras'],
  ['Pepino', 15, 0.7, 3.6, 0.1, '1 taza', 120, 'Verduras'],
  ['Zanahoria', 41, 0.9, 9.6, 0.2, '1 pieza', 61, 'Verduras'],
  ['Calabacita cocida', 17, 1.2, 3.1, 0.3, '1 taza', 180, 'Verduras'],
  ['Nopales cocidos', 15, 1.4, 3.3, 0.1, '1 taza', 149, 'Verduras'],
  ['Cebolla', 40, 1.1, 9.3, 0.1, '1/4 taza', 40, 'Verduras'],
  ['Chile jalapeño', 29, 0.9, 6.5, 0.4, '1 pieza', 14, 'Verduras'],
  ['Champiñones', 22, 3.1, 3.3, 0.3, '1 taza', 70, 'Verduras'],
  ['Ejotes cocidos', 35, 1.9, 7.9, 0.3, '1 taza', 125, 'Verduras'],
  ['Pimiento morrón', 31, 1, 6, 0.3, '1 pieza', 120, 'Verduras'],
  ['Coliflor cocida', 23, 1.8, 4.1, 0.5, '1 taza', 124, 'Verduras'],
  ['Chícharos cocidos', 84, 5.4, 15.6, 0.2, '1/2 taza', 80, 'Verduras'],

  // Grasas, semillas y aderezos
  ['Aceite (oliva o vegetal)', 884, 0, 0, 100, '1 cucharada', 14, 'Grasas'],
  ['Almendras', 579, 21.2, 21.6, 49.9, '1 puño', 28, 'Grasas'],
  ['Cacahuates', 567, 25.8, 16.1, 49.2, '1 puño', 28, 'Grasas'],
  ['Nueces', 654, 15.2, 13.7, 65.2, '1 puño', 28, 'Grasas'],
  ['Crema de cacahuate', 588, 25, 20, 50, '1 cucharada', 16, 'Grasas'],
  ['Semillas de chía', 486, 16.5, 42, 30.7, '1 cucharada', 12, 'Grasas'],
  ['Mayonesa', 680, 1, 0.6, 75, '1 cucharada', 14, 'Grasas'],
  ['Aderezo ranch', 430, 1, 6, 45, '1 cucharada', 15, 'Grasas'],
  ['Guacamole', 155, 2, 8.5, 14, '2 cucharadas', 30, 'Grasas'],
  ['Salsa roja o verde', 25, 1, 5, 0.3, '2 cucharadas', 30, 'Grasas'],

  // Platillos (estimados, dependen de la receta)
  ['Taco de bistec', 228, 13, 19, 11, '1 taco', 70, 'Platillos'],
  ['Taco al pastor', 235, 12, 20, 12, '1 taco', 70, 'Platillos'],
  ['Quesadilla de queso', 290, 13, 27, 15, '1 pieza', 90, 'Platillos'],
  ['Enchiladas verdes de pollo', 160, 10, 15, 7, '1 orden (3)', 350, 'Platillos'],
  ['Chilaquiles rojos', 180, 5, 20, 9, '1 plato', 300, 'Platillos'],
  ['Tamal', 210, 7, 22, 11, '1 pieza', 130, 'Platillos'],
  ['Pozole rojo', 70, 5.5, 7, 2.3, '1 plato', 450, 'Platillos'],
  ['Torta de jamón', 240, 11, 30, 8, '1 pieza', 250, 'Platillos'],
  ['Sopa de fideo', 60, 2, 9, 1.8, '1 plato', 250, 'Platillos'],
  ['Huevos a la mexicana', 150, 10, 3, 11, '1 porción', 150, 'Platillos'],
  ['Molletes', 250, 10, 30, 10, '2 mitades', 150, 'Platillos'],
  ['Gordita de chicharrón', 280, 9, 30, 14, '1 pieza', 120, 'Platillos'],
  ['Pizza de pepperoni', 290, 12, 32, 12.5, '1 rebanada', 110, 'Platillos'],
  ['Hamburguesa sencilla', 250, 13, 25, 11, '1 pieza', 180, 'Platillos'],
  ['Hot dog', 290, 10, 23, 18, '1 pieza', 100, 'Platillos'],
  ['Papas a la francesa', 312, 3.4, 41, 15, '1 orden mediana', 117, 'Platillos'],

  // Bebidas
  ['Refresco de cola', 42, 0, 10.6, 0, '1 lata (355 ml)', 355, 'Bebidas'],
  ['Jugo de naranja', 45, 0.7, 10.4, 0.2, '1 vaso (240 ml)', 240, 'Bebidas'],
  ['Café negro', 1, 0.1, 0, 0, '1 taza', 240, 'Bebidas'],
  ['Café latte (leche entera)', 56, 3, 4.5, 3, '1 vaso (350 ml)', 350, 'Bebidas'],
  ['Cerveza', 43, 0.5, 3.6, 0, '1 lata (355 ml)', 355, 'Bebidas'],
  ['Cerveza light', 29, 0.2, 1.6, 0, '1 lata (355 ml)', 355, 'Bebidas'],
  ['Vino tinto', 85, 0.1, 2.6, 0, '1 copa', 150, 'Bebidas'],
  ['Tequila o mezcal', 231, 0, 0, 0, '1 caballito', 45, 'Bebidas'],
  ['Agua de horchata', 60, 0.5, 13, 0.8, '1 vaso', 300, 'Bebidas'],

  // Snacks y dulces
  ['Papas fritas de bolsa', 536, 7, 53, 34, '1 bolsa', 45, 'Snacks'],
  ['Chocolate de leche', 535, 7.7, 59.4, 29.7, '1 barra', 40, 'Snacks'],
  ['Galletas con chispas de chocolate', 488, 5, 64, 24, '2 piezas', 30, 'Snacks'],
  ['Helado de vainilla', 207, 3.5, 24, 11, '1/2 taza', 66, 'Snacks'],
  ['Azúcar', 387, 0, 100, 0, '1 cucharadita', 4, 'Snacks'],
  ['Miel', 304, 0.3, 82.4, 0, '1 cucharada', 21, 'Snacks'],
  ['Mermelada', 278, 0.4, 69, 0.1, '1 cucharada', 20, 'Snacks'],
];

export const BASE_FOODS = RAW.map(([name, kcal, p, c, f, label, g, cat], i) => ({
  id: 'b' + i, src: 'base', name, kcal, p, c, f, cat,
  serving: { label, g },
}));

export const normalize = (s) => String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

// Every query word must appear somewhere in the name (accent-insensitive); names that start
// with the query rank first.
export function searchBase(q, limit = 25) {
  const words = normalize(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return BASE_FOODS
    .map((f) => ({ f, n: normalize(f.name) }))
    .filter(({ n }) => words.every((w) => n.includes(w)))
    .sort((a, b) => (b.n.startsWith(words[0]) - a.n.startsWith(words[0])) || a.n.length - b.n.length)
    .slice(0, limit)
    .map(({ f }) => f);
}
