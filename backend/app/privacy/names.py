"""Lexika für die Namenserkennung der PII-Schutzschicht.

Bewusst ausgelassen sind Vornamen, die gleichzeitig häufige Wörter im
Shop-Kontext sind (z. B. "Mark", "Bill", "Will", "May", "Jan", "April",
"Can", "Grace", "Hope", "Rose"), um Fehl-Anonymisierungen zu vermeiden.
"""

from __future__ import annotations

FIRST_NAMES: frozenset[str] = frozenset(
    name.lower()
    for name in """
    Aaron Adam Adrian Agnieszka Ahmed Ahmet Aisha Alexander Alexandra Alex Ali Alice Alina Amelie
    Amir Andrea Andreas Andrzej Angelika Anja Anke Anna Anne Annika Anton Antonia Ayse Barbara Bastian
    Ben Benedikt Benjamin Bernd Bettina Birgit Björn Brigitte Carina Carla Carlos Carmen Carolin Caroline
    Charlotte Chiara Chris Christian Christiane Christina Christine Christoph Clara Claudia Daniel Daniela
    David Deniz Dennis Dieter Dirk Dominik Doris Elena Elias Elif Elisabeth Ella Emil Emilia Emily Emir
    Emma Emre Erik Fabian Fatima Felix Finn Florian Franziska Frank Frederik Friedrich Gabriele Georg
    Gerhard Gisela Hanna Hannah Hannes Hans Harald Heike Heinz Helena Helga Helmut Henrik Hermann Holger
    Ines Ingrid Isabel Isabella Jakob James Janina Jana Jannik Jasmin Jennifer Jens Jessica Joachim Johanna
    Johannes John Jonas Jonathan Jörg Joseph Josef Julia Julian Juliane Jürgen Justin Kai Karin Karl
    Karsten Katharina Kathrin Katja Katrin Kerstin Kevin Klaus Konstantin Kristina Lara Laura Lea Lena
    Leon Leonie Lina Linda Lisa Louisa Luca Lucas Luis Luisa Lukas Maja Manfred Manuel Manuela Marco
    Marcel Maria Marie Mario Marion Markus Marta Martin Martina Mathias Matthias Max Maximilian Mehmet
    Melanie Mia Michael Michaela Michelle Mohammed Monika Moritz Mustafa Nadine Natalie Nicole Niklas
    Nils Nina Noah Nora Olaf Olga Oliver Oskar Pascal Patricia Patrick Paul Paula Peter Petra Philipp
    Piotr Rainer Ralf Ralph Rebecca Renate Robert Robin Roland Sabine Sabrina Sandra Sara Sarah Sascha
    Sebastian Selin Silke Simon Simone Sofia Sophia Sophie Stefan Stefanie Steffen Stephan Stephanie
    Susanne Sven Sylvia Tanja Thomas Thorsten Tim Timo Tobias Tom Torsten Ursula Ute Uwe Valentina
    Vanessa Vera Verena Viktoria Volker Walter Werner Wolfgang Yasmin Yusuf Zeynep
    Ashley Brian Charles Daniel Emily Eric George Jason Jeffrey Jennifer Joshua Karen Kenneth Kevin
    Kimberly Matthew Melissa Nancy Olivia Richard Ryan Sandra Stephen Steven Susan Thomas William
    Jacob Ethan Mason Logan Lucas Liam Ava Isabella Mia Harper Evelyn Abigail Madison Chloe
    """.split()
)

# Großgeschriebene Wörter, die nie Teil eines Personennamens sind
# (deutsche Substantive im Shop-Kontext, Funktionswörter, Grußformeln).
NON_NAME_TOKENS: frozenset[str] = frozenset(
    word.lower()
    for word in """
    Ich Sie Du Wir Ihr Er Es Mein Meine Meinen Meinem Meiner Ihre Ihren Ihrem Unser Unsere Bitte Danke
    Hallo Hi Hey Moin Servus Liebe Lieber Sehr Guten Tag Morgen Abend Und Oder Aber Die Der Das Den Dem
    Des Ein Eine Einen Mit Von Vom Aus Bei Für Im In Am An Auf Zum Zur Nach Seit Wie Was Wann Warum Wo
    Leider Heute Gestern Morgen Jetzt Noch Schon Grüße Grüsse Gruß Gruss Team Shop Service Support
    Kundenservice Kundendienst Zusammen Bestellung Bestellnummer Paket Lieferung Rechnung Ware Artikel
    Produkt Kunde Kundin Problem Frage Geld Rückerstattung Retoure Erstattung Zahlung Versand Adresse
    The I My Me Please Thanks Thank Hello Dear And Or But With From For In On At To Of Order Package
    Invoice Payment Refund Return Regards Wishes Best Kind Sincerely Yours Customer Team Hotline
    Montag Dienstag Mittwoch Donnerstag Freitag Samstag Sonntag Januar Februar März Juni Juli August
    September Oktober November Dezember Monday Tuesday Wednesday Thursday Friday Saturday Sunday
    Deutschland Germany Österreich Schweiz Berlin Hamburg München Köln Frankfurt Stuttgart DHL DPD
    Hermes GLS UPS PayPal Klarna Amazon Ebay Zalando
    """.split()
)
