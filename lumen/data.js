// Catálogo de ejemplo. Todos los títulos y sinopsis son inventados.
// Los videos de muestra son cortometrajes abiertos de la Blender Foundation (CC BY).
const VIDEOS = {
  bunny: { src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4", credit: "Big Buck Bunny — Blender Foundation (CC BY 3.0)" },
  dream: { src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4", credit: "Elephants Dream — Blender Foundation (CC BY 2.5)" },
  sintel: { src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4", credit: "Sintel — Blender Foundation (CC BY 3.0)" },
  steel: { src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4", credit: "Tears of Steel — Blender Foundation (CC BY 3.0)" },
};

const TITLES = [
  { id: "marea-baja", title: "Marea Baja", year: 2025, type: "Serie", rating: "16+", seasons: 2, genres: ["Drama", "Suspenso"], hue: 200, video: "steel",
    synopsis: "En un pueblo costero, una buzo descubre que el mar devuelve objetos de personas que aún no han desaparecido." },
  { id: "ciudad-de-cobre", title: "Ciudad de Cobre", year: 2024, type: "Película", rating: "13+", duration: "1 h 52 min", genres: ["Ciencia ficción", "Acción"], hue: 28, video: "steel",
    synopsis: "Una mecánica de drones y un robot obsoleto intentan apagar la red que controla la ciudad antes del amanecer." },
  { id: "el-ultimo-faro", title: "El Último Faro", year: 2023, type: "Película", rating: "7+", duration: "1 h 31 min", genres: ["Aventura", "Familiar"], hue: 48, video: "sintel",
    synopsis: "Dos hermanos cruzan un archipiélago para encender el faro que guía a las aves migratorias de regreso a casa." },
  { id: "conejo-de-bosque", title: "El Guardián del Bosque", year: 2022, type: "Película", rating: "TP", duration: "10 min", genres: ["Animación", "Comedia"], hue: 110, video: "bunny",
    synopsis: "Un gigante tranquilo del bosque decide darle una lección a tres roedores que no dejan de molestar." },
  { id: "maquinas-sonando", title: "Máquinas Soñando", year: 2021, type: "Película", rating: "13+", duration: "11 min", genres: ["Animación", "Surrealista"], hue: 275, video: "dream",
    synopsis: "Dos viajeros recorren una máquina infinita donde cada puerta conduce a un recuerdo distinto." },
  { id: "dragona", title: "Escamas", year: 2020, type: "Película", rating: "13+", duration: "15 min", genres: ["Animación", "Fantasía"], hue: 12, video: "sintel",
    synopsis: "Una guerrera recorre tierras heladas buscando a la pequeña criatura alada que crió como si fuera su familia." },
  { id: "kilometro-cero", title: "Kilómetro Cero", year: 2025, type: "Serie", rating: "16+", seasons: 1, genres: ["Crimen", "Drama"], hue: 340, video: "steel",
    synopsis: "Una periodista de nota roja sigue la pista de un taxista que nunca recoge al mismo pasajero dos veces." },
  { id: "sal-y-limon", title: "Sal y Limón", year: 2024, type: "Serie", rating: "13+", seasons: 3, genres: ["Comedia", "Cocina"], hue: 85, video: "bunny",
    synopsis: "Cuatro amigos heredan una fonda en ruinas y tienen un verano para convertirla en el lugar de moda." },
  { id: "orbita", title: "Órbita", year: 2023, type: "Documental", rating: "TP", duration: "58 min", genres: ["Documental", "Ciencia"], hue: 230, video: "dream",
    synopsis: "La historia de los satélites caseros construidos por estudiantes de preparatoria en América Latina." },
  { id: "la-casa-del-eco", title: "La Casa del Eco", year: 2022, type: "Película", rating: "18+", duration: "1 h 44 min", genres: ["Terror", "Suspenso"], hue: 0, video: "dream",
    synopsis: "Cada palabra que se dice dentro de la casa se repite al día siguiente… con una voz distinta." },
  { id: "pulso", title: "Pulso", year: 2025, type: "Serie", rating: "16+", seasons: 1, genres: ["Acción", "Thriller"], hue: 160, video: "steel",
    synopsis: "Una paramédica descubre que puede ver los últimos diez segundos antes de cada accidente." },
  { id: "vientos-del-norte", title: "Vientos del Norte", year: 2021, type: "Serie", rating: "13+", seasons: 4, genres: ["Drama", "Histórico"], hue: 32, video: "sintel",
    synopsis: "Tres generaciones de una familia ganadera enfrentan la sequía, la revolución y un secreto enterrado." },
  { id: "pixel-perdido", title: "Píxel Perdido", year: 2024, type: "Película", rating: "7+", duration: "1 h 27 min", genres: ["Animación", "Aventura"], hue: 300, video: "bunny",
    synopsis: "Un personaje de videojuego abandonado escapa de su consola para encontrar a la niña que lo diseñó." },
  { id: "raices", title: "Raíces", year: 2020, type: "Documental", rating: "TP", duration: "1 h 10 min", genres: ["Documental", "Naturaleza"], hue: 130, video: "sintel",
    synopsis: "Un año en la vida de un bosque de niebla, contado desde el suelo hasta las copas de los árboles." },
  { id: "doble-turno", title: "Doble Turno", year: 2023, type: "Serie", rating: "16+", seasons: 2, genres: ["Comedia", "Drama"], hue: 190, video: "bunny",
    synopsis: "Una enfermera de noche y un panadero de madrugada comparten departamento sin haberse visto nunca." },
  { id: "senal", title: "Señal", year: 2024, type: "Película", rating: "16+", duration: "1 h 38 min", genres: ["Ciencia ficción", "Suspenso"], hue: 255, video: "dream",
    synopsis: "Un radioaficionado recibe mensajes de una estación que fue desmantelada hace cuarenta años." },
];

const ROWS = [
  { name: "Tendencias ahora", ids: ["marea-baja", "kilometro-cero", "pulso", "ciudad-de-cobre", "senal", "sal-y-limon", "la-casa-del-eco"] },
  { name: "Nuevos lanzamientos", filter: (t) => t.year >= 2024 },
  { name: "Series para maratonear", filter: (t) => t.type === "Serie" },
  { name: "Animación", filter: (t) => t.genres.includes("Animación") },
  { name: "Suspenso y terror", filter: (t) => t.genres.some((g) => ["Suspenso", "Terror", "Thriller"].includes(g)) },
  { name: "Documentales", filter: (t) => t.type === "Documental" },
];
