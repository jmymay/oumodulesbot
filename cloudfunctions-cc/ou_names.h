#ifndef __OUMODULESBOT_CLOUDFUNCTIONS_CC_INTERACTION_OU_NAMES_H_
#define __OUMODULESBOT_CLOUDFUNCTIONS_CC_INTERACTION_OU_NAMES_H_

#include <cctype>
#include <fstream>
#include <iterator>
#include <string_view>

#include <boost/regex.hpp>
#include <nlohmann/json.hpp>

namespace ou_modules_bot {

namespace {
inline boost::regex &GetOURegex() {
  static boost::regex ou_regex("[a-zA-Z]{1,6}[0-9]{1,3}(?:-[a-zA-Z]{1,5})?|[a-"
                               "zA-Z][0-9]{2}(?:-[a-zA-Z]{1,5})?|[qQ][dD]");
  return ou_regex;
}
} // namespace

class OUNames {
public:
  OUNames(std::string message) : message_(message) {
    std::ifstream file("cache.json");
    file >> cache_;
  }

  struct Iterator {
    Iterator(const std::string& message, nlohmann::json *cache) {
      cache_ = cache;
      flags_ = boost::match_default;
      message_ = message;
    }

    bool NextItem(nlohmann::json::reference item) {
      std::string_view message_view = message_;
      auto start = (flags_ & boost::match_prev_avail) ? match_[0].second
                                                      : message_view.begin();
      if (boost::regex_search(start, message_view.end(), match_, GetOURegex(),
                              flags_)) {
        flags_ |= boost::match_prev_avail;
        flags_ |= boost::match_not_bob;
        item = ResolveItem(std::string((const char *)match_[0].first,
                                       match_[0].second - match_[0].first));
        return true;
      }
      return false;
    }

  private:
    friend class OUNames;

    nlohmann::json ResolveItem(const std::string &name) {
      std::string uppercase = name;
      std::transform(name.begin(), name.end(), uppercase.begin(),
                     [](unsigned char c) { return std::toupper(c); });
      auto result = (*cache_)[uppercase];
      if (result.is_null()) {
        return nullptr;
      }
      return {
          {"code", uppercase}, {"full_name", result[0]}, {"url", result[1]}};
    }

    std::string message_;
    boost::match_flag_type flags_;
    boost::match_results<std::string_view::const_iterator> match_;

    nlohmann::json *cache_;
  };

  Iterator GetIterator() { return Iterator(message_, &cache_); }

private:
  std::string message_;
  nlohmann::json cache_;
};

} // namespace ou_modules_bot
#endif // __OUMODULESBOT_CLOUDFUNCTIONS_CC_INTERACTION_OU_NAMES_H_
