# Herkunft der Galeriebilder

Die Bilder in diesem Ordner erscheinen in der Web-Oberfläche während des Gesprächs in der
Galerie neben dem Chat (`static/index.html`). Sie sind reine Stimmungsbilder und stehen in keinem
Zusammenhang mit dem später geplanten Reiseziel. Jedes Bild wird unten mit dem Text der Spalte
„Motiv" und dem Bildnachweis „Foto: Fotograf / Unsplash" beschriftet (`GALERIE_BILDER` in
`static/index.html`, Übereinstimmung geprüft in `tests/test_galerie.py`). Alle Fotos stammen von
Unsplash und stehen unter der Unsplash License (https://unsplash.com/license): kostenlose Nutzung
auch für kommerzielle Zwecke, keine Genehmigung erforderlich, Namensnennung nicht verpflichtend,
hier aber angegeben.

Die Dateien wurden einmalig über das Unsplash-Bild-CDN (`images.unsplash.com`) in reduzierter
Auflösung heruntergeladen (Parameter `w`, `q`, `fm=jpg`, jeweils unter 300 KB) und werden lokal
ausgeliefert; zur Laufzeit erfolgt keine externe Bildanfrage. Fotograf, Lizenzhinweis („Free") und
Bildadresse wurden der jeweiligen Unsplash-Fotoseite entnommen, gelesen über deren archivierte
Kopie im Internet Archive, da unsplash.com automatisierte Abrufe mit einer Bot-Prüfung blockiert.
Ausgewählt wurden nur als „Free" gekennzeichnete Fotos, keine Unsplash+-Fotos.

| Datei | Motiv | Fotograf | Unsplash-Seite | Lizenz |
|---|---|---|---|---|
| alpensee_toblino.jpg | Lago di Toblino mit Burg, Trentino (Italien) | Marc St (@marcst84) | https://unsplash.com/photos/lake-across-mountain-and-trees-6ajQ-lAszvs | Unsplash License |
| kueste_manarola.jpg | Manarola, Cinque Terre (Italien), Abendstimmung | Justin Owens (@jwowens) | https://unsplash.com/photos/cinque-terre-italy-DsS4q5L9llo | Unsplash License |
| lavendelfeld.jpg | Lavendelfeld bei Zetyovo (Bulgarien) | Nikolay Hristov (@nikolayh) | https://unsplash.com/photos/lavender-field-during-daytime-zGJoz7TIpcw | Unsplash License |
| bahn_alpen_schweiz.jpg | Rote Bergbahn vor Gletschern (Schweiz) | Patrick Robert Doyle (@teapowered) | https://unsplash.com/photos/red-train-near-mountain-alps-QmM7e2vrZnU | Unsplash License |
| bahn_viadukt_filisur.jpg | Bernina Express auf einem Steinviadukt bei Filisur (Schweiz) | Robin Ulrich (@rocoweb) | https://unsplash.com/photos/red-train-on-brown-bridge-Xd8AaJK61Ak | Unsplash License |
| see_luzern.jpg | Vierwaldstättersee bei Luzern (Schweiz) | Karsten Winegeart (@_karsten) | https://unsplash.com/photos/lake-and-mountains-in-lucerne-FigFdwc0iEs | Unsplash License |
| see_bled.jpg | Bleder See mit Inselkirche (Slowenien) | QQ Z (@azhen__) | https://unsplash.com/photos/lake-bled-with-an-island-church-and-majestic-mountains-sPrhVJDrFH4 | Unsplash License |
| weinberge_toskana.jpg | Weinberge in der Toskana (Italien) | Johny Goerend (@johnygoerend) | https://unsplash.com/photos/vineyard-rows-on-tuscan-hillside-pnigODapPek | Unsplash License |
| fjord_norwegen.jpg | Fjord mit Wolkenbergen (Norwegen) | Marek Piwnicki (@marekpiwnicki) | https://unsplash.com/photos/fjord-surrounded-by-dramatic-cloud-covered-mountains-jMPwiaqRXzI | Unsplash License |
| kuppel_santorini.jpg | Blaue Kirchenkuppel mit Bougainvillea, Oia, Santorini (Griechenland) | Xuan Nguyen (@darthxuan) | https://unsplash.com/photos/santorini-dome-chapel-greece-E2XzMe-XmiE | Unsplash License |
