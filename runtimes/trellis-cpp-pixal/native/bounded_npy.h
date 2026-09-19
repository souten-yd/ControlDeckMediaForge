#pragma once
// Strict reader for our private NumPy v1 little-endian F32 C-order interchange.
// Validate header/product/exact file size before allocating tensor storage.
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>

namespace mediaforge::pixal {
struct InputArray { std::vector<size_t> shape; std::vector<float> data; };
inline InputArray read_input_array(const std::filesystem::path& path,size_t max_elements) {
    std::ifstream stream(path,std::ios::binary);
    unsigned char prefix[10]{};
    stream.read(reinterpret_cast<char*>(prefix),10);
    if (!stream || std::memcmp(prefix,"\x93NUMPY\x01\x00",8))
        throw std::invalid_argument("invalid worker NPY v1 prefix");
    size_t header_size=size_t(prefix[8])+(size_t(prefix[9])<<8);
    if (!header_size || header_size>4096) throw std::invalid_argument("worker NPY header exceeds bound");
    std::string header(header_size,'\0');stream.read(header.data(),header_size);
    std::smatch match;
    const std::regex format(R"(^\{'descr': '<f4', 'fortran_order': False, 'shape': \(([0-9, ]+)\), \}[ \n]*$)");
    if (!stream || !std::regex_match(header,match,format)) throw std::invalid_argument("invalid worker NPY layout");
    InputArray result;size_t count=1;
    std::string dimensions=match[1];
    const std::regex dimension(R"(^ *([1-9][0-9]*) *(,|$))");
    while (!dimensions.empty()) {
        if (!std::regex_search(dimensions,match,dimension)) throw std::invalid_argument("invalid worker NPY shape");
        if (match[1].length()>8) throw std::invalid_argument("worker NPY dimension exceeds bound");
        size_t value=std::stoull(match[1]);
        if (result.shape.size()>=3 || value>max_elements || count>max_elements/value)
            throw std::invalid_argument("worker NPY tensor exceeds bound");
        result.shape.push_back(value);count*=value;dimensions=match.suffix();
    }
    if (result.shape.empty() || std::filesystem::file_size(path)!=10+header_size+count*sizeof(float))
        throw std::invalid_argument("worker NPY payload size differs");
    uint16_t endian=1;
    if (*reinterpret_cast<unsigned char*>(&endian)!=1) throw std::runtime_error("little-endian worker required");
    result.data.resize(count);stream.read(reinterpret_cast<char*>(result.data.data()),count*sizeof(float));
    if (!stream || stream.peek()!=std::char_traits<char>::eof()) throw std::invalid_argument("worker NPY payload changed");
    for (float value:result.data) if (!std::isfinite(value)) throw std::invalid_argument("non-finite worker input");
    return result;
}
}
