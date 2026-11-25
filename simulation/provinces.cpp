// Individual speakers and contact networks in a Roman-inspired artificial society.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using std::array;
using std::string;
using std::vector;
namespace fs = std::filesystem;

constexpr int towns = 6, meanings = 24, forms = 2500;
constexpr uint16_t unknown = 65535;
struct Word {
    uint32_t root;
    uint16_t form;
};
struct Person {
    array<Word, meanings> spoken{};
    array<uint16_t, meanings> heard{};
    int id;
};

// Fixed, independently addressed streams keep interventions paired even when outcomes differ.
struct Random {
    uint64_t state;
    uint64_t next() {
        uint64_t x = (state += 0x9e3779b97f4a7c15ULL);
        x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
        x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
        return x ^ (x >> 31);
    }
    int pick(int n) { return int((uint64_t(uint32_t(next())) * n) >> 32); }
};
Random stream(int seed, int round, int purpose, int index = 0) {
    Random r{(uint64_t(seed) << 32) | uint32_t(round)};
    r.state = r.next() ^ (uint64_t(purpose) << 32) ^ uint32_t(index);
    return r;
}
int other(int current, int count, Random &r) { return (current + 1 + r.pick(count - 1)) % count; }

vector<Person> founders(int seed, int size) {
    auto rng = stream(seed, 0, 1);
    array<uint16_t, meanings> base{};
    for (int m = 0; m < meanings; ++m) {
        uint16_t f;
        do {
            f = rng.pick(forms);
        } while (std::find(base.begin(), base.begin() + m, f) != base.begin() + m);
        base[m] = f;
    }
    vector<Person> people(size * towns);
    for (int i = 0; i < int(people.size()); ++i) {
        people[i].id = i;
        people[i].heard.fill(unknown);
        for (int m = 0; m < meanings; ++m)
            people[i].spoken[m] = {uint32_t(m), base[m]};
    }
    return people;
}

bool knows(const Person &listener, int meaning, int form) {
    return listener.spoken[meaning].form == form || listener.heard[meaning] == form;
}
// Four visible objects. Credit only unambiguous recognition of the intended object.
bool recognized(const Person &listener, int m, int form, int distractors) {
    if (!knows(listener, m, form))
        return false;
    for (int k : {0, 7, 15}) {
        int alternative = (m + 1 + (distractors + k) % (meanings - 1)) % meanings;
        if (knows(listener, alternative, form))
            return false;
    }
    return true;
}

enum class Network { common, empire, open, sealed };
const char *name(Network n) {
    switch (n) {
    case Network::common:
        return "common";
    case Network::empire:
        return "breakup";
    case Network::open:
        return "open";
    case Network::sealed:
        return "sealed";
    }
    throw std::logic_error("network");
}

struct Counts {
    int64_t conversations = 0, remote = 0, understood = 0, repairs = 0, adoptions = 0, coins = 0,
            births = 0;
    array<array<int64_t, towns>, towns> routes{};
};
struct Files {
    std::ofstream intervals, routes, vocabulary, trace;
    explicit Files(const fs::path &out)
        : intervals(out / "intervals.csv"), routes(out / "routes.csv"),
          vocabulary(out / "vocabulary.csv"), trace(out / "trace.csv") {
        for (auto *f : {&intervals, &routes, &vocabulary, &trace})
            f->exceptions(std::ios::failbit | std::ios::badbit);
        intervals
            << "history,round,conversations,remote,understood,repairs,adoptions,coins,births,"
               "remote_probe_hits,remote_probes,local_probe_hits,local_probes,same_remote_form\n";
        routes << "history,round,listener_town,speaker_town,conversations\n";
        vocabulary << "history,round,town,meaning,modal_form,speakers,total\n";
        trace << "round,lineage,speaker,listener,speaker_town,listener_town,form,coined,understood,"
                 "repaired,adopted\n";
    }
};

int shifted(int form, int position, int from, int to) {
    constexpr array<int, 4> place{250, 50, 5, 1}, radix{10, 5, 10, 5};
    return (form / place[position]) % radix[position] == from ? form + (to - from) * place[position]
                                                              : form;
}

// Successors learn their vocabulary from two local tutors. Changes in pronunciation
// start in a subset of a town and affect the same sound position across multiple words.
void turnover(vector<Person> &p, int size, int seed, int round, Counts &c) {
    const auto old = p;
    for (int town = 0; town < towns; ++town) {
        auto rng = stream(seed, round, 2, town);
        int pos = rng.pick(4), radix = (pos % 2 ? 5 : 10), from = rng.pick(radix),
            to = other(from, radix, rng);
        for (int i = 0; i < size; ++i) {
            int id = town * size + i;
            if (rng.pick(100) < 8) {
                int a = town * size + other(i, size, rng), b = town * size + other(i, size, rng);
                p[id].id = round * int(p.size()) + id;
                p[id].heard.fill(unknown);
                for (int m = 0; m < meanings; ++m)
                    p[id].spoken[m] = old[rng.pick(2) ? a : b].spoken[m];
                ++c.births;
            }
            if (rng.pick(100) < 30) {
                for (int m = 0; m < meanings; ++m) {
                    Word &w = p[id].spoken[m];
                    auto updated = shifted(w.form, pos, from, to);
                    if (updated != w.form) {
                        p[id].heard[m] = w.form;
                        w.form = updated;
                    }
                }
            }
        }
    }
}

void round_of_talk(vector<Person> &p, int size, int seed, int t, int rounds, Network history,
                   Counts &count, Files &files) {
    bool fractured = t > rounds / 10 && t <= 7 * rounds / 10;
    int rate = fractured && history == Network::sealed   ? 0
               : fractured && history == Network::empire ? 3
                                                         : 25;
    int total = int(p.size());
    auto order = stream(seed, t, 3);
    int offset = order.pick(total);
    for (int j = 0; j < total; ++j) {
        int dst = (offset + j) % total, town = dst / size, local = dst % size;
        auto rng = stream(seed, t, 4, dst);
        bool cross = rng.pick(100) < rate;
        int route = rng.pick(1000000), peer = rng.pick(size), near = rng.pick(100);
        int other_town = town;
        if (cross) {
            if (fractured && history == Network::empire)
                other_town = town == 0           ? 1
                             : town == towns - 1 ? towns - 2
                                                 : town + (route < 500000 ? -1 : 1);
            else
                other_town = (town + 1 + route / (1000000 / (towns - 1))) % towns;
        } else {
            // A familiar circle of up to eight neighbors in either direction.
            int radius = std::min(8, (size - 1) / 2);
            int hop = near < 60 ? (route % radius + 1) * (route < 500000 ? -1 : 1)
                                : 1 + int(int64_t(route) * (size - 1) / 1000000);
            peer = (local + size + hop) % size;
        }
        Person &speaker = p[other_town * size + peer], &listener = p[dst];
        int m = rng.pick(meanings), distractors = rng.pick(meanings - 1);
        bool coin = rng.pick(4000) == 0;
        uint16_t novel = rng.pick(forms);
        bool can_repair = rng.pick(100) < 55, copy_known = rng.pick(100) < 34,
             copy_new = rng.pick(100) < 12;
        Word &word = speaker.spoken[m];
        if (coin) {
            speaker.heard[m] = word.form;
            word = {uint32_t(meanings + (t - 1) * total + dst), novel};
        }
        bool first = recognized(listener, m, word.form, distractors);
        bool repair = !first && can_repair;
        bool adopt = (first || repair) && listener.spoken[m].form != word.form &&
                     (first ? copy_known : copy_new);
        if (adopt) {
            listener.heard[m] = listener.spoken[m].form;
            listener.spoken[m] = word;
        } else if (repair && listener.spoken[m].form != word.form)
            listener.heard[m] = word.form;
        ++count.conversations;
        ++count.routes[town][other_town];
        count.remote += cross;
        count.understood += first;
        count.repairs += repair;
        count.adoptions += adopt;
        count.coins += coin;
        if (seed == 1 && history == Network::empire && m == 0 &&
            word.root >= uint32_t(meanings + rounds / 10 * total) && (coin || adopt))
            files.trace << t << ',' << word.root << ',' << speaker.id << ',' << listener.id << ','
                        << other_town << ',' << town << ',' << word.form << ',' << coin << ','
                        << first << ',' << repair << ',' << adopt << '\n';
    }
    if (t % 40 == 0)
        turnover(p, size, seed, t, count);
}

void snapshot(const vector<Person> &p, int size, int seed, int t, Network history, Counts &c,
              Files &files) {
    int remote_hits = 0, remote_tests = 0, local_hits = 0, local_tests = 0, same = 0;
    auto rng = stream(seed, t, 5);
    for (int a = 0; a < towns; ++a)
        for (int b = 0; b < towns; ++b) {
            files.routes << name(history) << ',' << t << ',' << a << ',' << b << ','
                         << c.routes[a][b] << '\n';
            for (int m = 0; m < meanings; ++m)
                for (int probe = 0; probe < 32; ++probe) {
                    int i = rng.pick(size), j = rng.pick(size);
                    if (a == b && i == j)
                        j = (j + 1) % size;
                    auto &listener = p[a * size + i];
                    auto form = p[b * size + j].spoken[m].form;
                    bool hit = recognized(listener, m, form, rng.pick(meanings - 1));
                    if (a == b) {
                        local_hits += hit;
                        ++local_tests;
                    } else {
                        remote_hits += hit;
                        ++remote_tests;
                        same += listener.spoken[m].form == form;
                    }
                }
        }
    files.intervals << name(history) << ',' << t << ',' << c.conversations << ',' << c.remote << ','
                    << c.understood << ',' << c.repairs << ',' << c.adoptions << ',' << c.coins
                    << ',' << c.births << ',' << remote_hits << ',' << remote_tests << ','
                    << local_hits << ',' << local_tests << ',' << same << '\n';
    if (seed == 1)
        for (int a = 0; a < towns; ++a)
            for (int m = 0; m < meanings; ++m) {
                array<int, forms> counts{};
                for (int i = 0; i < size; ++i)
                    ++counts[p[a * size + i].spoken[m].form];
                auto peak = std::max_element(counts.begin(), counts.end());
                files.vocabulary << name(history) << ',' << t << ',' << a << ',' << m << ','
                                 << (peak - counts.begin()) << ',' << *peak << ',' << size << '\n';
            }
    c = Counts{};
}

int main(int argc, char **argv) {
    try {
        if (argc != 5)
            throw std::invalid_argument("usage: provinces SEED SPEAKERS_PER_TOWN ROUNDS OUTPUT");
        int seed = std::stoi(argv[1]), size = std::stoi(argv[2]), rounds = std::stoi(argv[3]);
        if (seed < 1 || size < 3 || rounds < 40 || rounds % 20 ||
            int64_t(size) * towns * (int64_t(rounds) + 1) > INT32_MAX - meanings)
            throw std::invalid_argument(
                "invalid seed, population or rounds (multiple of 20 required)");
        Files files(argv[4]);
        auto start = founders(seed, size);
        Counts c;
        auto advance = [&](vector<Person> &people, int begin, int end, Network history) {
            for (int t = begin; t <= end; ++t) {
                round_of_talk(people, size, seed, t, rounds, history, c, files);
                if (t % (rounds / 20) == 0)
                    snapshot(people, size, seed, t, history, c, files);
            }
        };
        snapshot(start, size, seed, 0, Network::common, c, files);
        advance(start, 1, rounds / 10, Network::common);
        for (auto history : {Network::empire, Network::open, Network::sealed}) {
            auto people = start;
            advance(people, rounds / 10 + 1, rounds, history);
        }
        return 0;
    } catch (const std::exception &ex) {
        std::cerr << ex.what() << '\n';
        return 1;
    }
}
